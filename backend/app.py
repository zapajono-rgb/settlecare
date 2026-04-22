import json
import os
import logging
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

import stripe

from models import db, User, ClassAction, EligibilityQuestion, UserResult, QuizAnswer, UserArchive

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///class_actions.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
CORS(app, origins=cors_origins, supports_credentials=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db.init_app(app)
with app.app_context():
    db.create_all()

token_serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

# Stripe config
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_MONTHLY = os.getenv("STRIPE_PRICE_MONTHLY", "")  # price_xxx from Stripe dashboard
STRIPE_PRICE_YEARLY = os.getenv("STRIPE_PRICE_YEARLY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


# --- Auth helpers ---
def make_token(user_id):
    return token_serializer.dumps(user_id, salt="auth")


def verify_token(token):
    try:
        user_id = token_serializer.loads(token, salt="auth", max_age=86400 * 30)
        return user_id
    except (BadSignature, SignatureExpired):
        return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Login required"}), 401
        user_id = verify_token(auth[7:])
        if not user_id:
            return jsonify({"error": "Invalid or expired session"}), 401
        g.user = db.session.get(User, user_id)
        if not g.user:
            return jsonify({"error": "User not found"}), 401
        return f(*args, **kwargs)
    return decorated


def optional_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        g.user = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            user_id = verify_token(auth[7:])
            if user_id:
                g.user = db.session.get(User, user_id)
        return f(*args, **kwargs)
    return decorated


# --- Auth endpoints ---
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"token": make_token(user.id), "user": user.to_dict()}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    return jsonify({"token": make_token(user.id), "user": user.to_dict()})


@app.route("/api/auth/me", methods=["GET"])
@login_required
def me():
    return jsonify({"user": g.user.to_dict()})


# --- Class actions ---
@app.route("/api/class-actions", methods=["GET"])
@optional_auth
def list_class_actions():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()

    query = ClassAction.query
    if search:
        query = ClassAction.search(search)
    if status:
        query = query.filter(ClassAction.status == status)

    query = query.order_by(ClassAction.status.asc(), ClassAction.updated_at.desc())
    cases = query.all()

    # If user is logged in, attach results + archive status
    user_results = {}
    archived_ids = set()
    if g.user:
        results = UserResult.query.filter_by(user_id=g.user.id).all()
        user_results = {r.class_action_id: r.is_eligible for r in results}
        archives = UserArchive.query.filter_by(user_id=g.user.id).all()
        archived_ids = {a.class_action_id for a in archives}

    case_list = []
    for c in cases:
        d = c.to_dict()
        d["question_count"] = len(c.questions)
        if g.user:
            d["user_checked"] = c.id in user_results
            d["user_eligible"] = user_results.get(c.id)
            d["archived"] = c.id in archived_ids
        case_list.append(d)

    return jsonify({"cases": case_list})


@app.route("/api/class-actions/<int:case_id>", methods=["GET"])
@optional_auth
def get_class_action(case_id):
    case = db.session.get(ClassAction, case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404

    d = case.to_dict(include_questions=True)
    d["question_count"] = len(case.questions)

    if g.user:
        result = UserResult.query.filter_by(
            user_id=g.user.id, class_action_id=case_id
        ).first()
        d["user_checked"] = result is not None
        d["user_eligible"] = result.is_eligible if result else None
        d["user_answers"] = json.loads(result.answers_json) if result else None

    return jsonify(d)


# --- Eligibility questionnaire ---
@app.route("/api/class-actions/<int:case_id>/submit", methods=["POST"])
@login_required
def submit_eligibility(case_id):
    case = db.session.get(ClassAction, case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404

    # Check if user has remaining free checks
    if not g.user.can_check:
        return jsonify({
            "error": "upgrade_required",
            "message": "You've used all 3 free eligibility checks. Upgrade to Premium for unlimited checks.",
        }), 403

    data = request.get_json() or {}
    answers = data.get("answers", {})  # {question_id: true/false}

    if not answers:
        return jsonify({"error": "No answers provided"}), 400

    # Check eligibility: user must match required_answer for every question
    is_eligible = True
    for q in case.questions:
        user_answer = answers.get(str(q.id))
        if user_answer is None:
            return jsonify({"error": f"Missing answer for question {q.id}"}), 400
        if bool(user_answer) != q.required_answer:
            is_eligible = False

    # Upsert result
    existing = UserResult.query.filter_by(
        user_id=g.user.id, class_action_id=case_id
    ).first()
    if existing:
        existing.is_eligible = is_eligible
        existing.answers_json = json.dumps(answers)
        existing.created_at = datetime.utcnow()
    else:
        result = UserResult(
            user_id=g.user.id,
            class_action_id=case_id,
            is_eligible=is_eligible,
            answers_json=json.dumps(answers),
        )
        db.session.add(result)

    # Increment check count for free users
    if not g.user.is_premium:
        g.user.checks_used = (g.user.checks_used or 0) + 1

    db.session.commit()

    resp = {
        "is_eligible": is_eligible,
        "case_name": case.case_name,
        "defendant": case.defendant,
    }
    if is_eligible:
        resp["claim_portal_url"] = case.claim_portal_url
        resp["law_firm"] = case.law_firm
        resp["law_firm_contact"] = case.law_firm_contact
        resp["law_firm_website"] = case.law_firm_website

    return jsonify(resp)


# --- User's results dashboard ---
@app.route("/api/my-results", methods=["GET"])
@login_required
def my_results():
    results = (
        UserResult.query
        .filter_by(user_id=g.user.id)
        .order_by(UserResult.created_at.desc())
        .all()
    )
    return jsonify({"results": [r.to_dict() for r in results]})


# --- Quiz: one screening question per case ---
@app.route("/api/quiz", methods=["GET"])
@login_required
def get_quiz():
    """Get all cases with their first question for the quick-screen quiz."""
    cases = ClassAction.query.order_by(ClassAction.id).all()
    existing = {a.class_action_id: a.answer for a in
                QuizAnswer.query.filter_by(user_id=g.user.id).all()}

    items = []
    for c in cases:
        if not c.questions:
            continue
        # Use the second question (index 1) as screening — it's usually the
        # customer/product relationship question. Fall back to first.
        screen_q = c.questions[1] if len(c.questions) > 1 else c.questions[0]
        items.append({
            "case_id": c.id,
            "case_name": c.case_name,
            "defendant": c.defendant,
            "settlement_amount": c.settlement_amount,
            "question": screen_q.question_text,
            "answer": existing.get(c.id),
        })

    answered = sum(1 for it in items if it["answer"] is not None)
    return jsonify({
        "items": items,
        "total": len(items),
        "answered": answered,
        "completed": g.user.quiz_completed,
    })


@app.route("/api/quiz/answer", methods=["POST"])
@login_required
def save_quiz_answer():
    data = request.get_json() or {}
    case_id = data.get("case_id")
    answer = data.get("answer")  # "yes", "no", "not_sure"

    if not case_id or answer not in ("yes", "no", "not_sure"):
        return jsonify({"error": "case_id and answer (yes/no/not_sure) required"}), 400

    existing = QuizAnswer.query.filter_by(
        user_id=g.user.id, class_action_id=case_id
    ).first()
    if existing:
        existing.answer = answer
    else:
        qa = QuizAnswer(user_id=g.user.id, class_action_id=case_id, answer=answer)
        db.session.add(qa)

    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/quiz/complete", methods=["POST"])
@login_required
def complete_quiz():
    g.user.quiz_completed = True
    db.session.commit()
    return jsonify({"ok": True})


# --- Archive ---
@app.route("/api/archive/<int:case_id>", methods=["POST"])
@login_required
def archive_case(case_id):
    existing = UserArchive.query.filter_by(
        user_id=g.user.id, class_action_id=case_id
    ).first()
    if not existing:
        db.session.add(UserArchive(user_id=g.user.id, class_action_id=case_id))
        db.session.commit()
    return jsonify({"archived": True})


@app.route("/api/archive/<int:case_id>", methods=["DELETE"])
@login_required
def unarchive_case(case_id):
    existing = UserArchive.query.filter_by(
        user_id=g.user.id, class_action_id=case_id
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
    return jsonify({"archived": False})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})


# --- Admin: trigger auto-scraper ---
# --- Stripe billing ---
@app.route("/api/billing/checkout", methods=["POST"])
@login_required
def create_checkout():
    if not stripe.api_key:
        return jsonify({"error": "Payments not configured yet"}), 503
    data = request.get_json() or {}
    plan = data.get("plan", "monthly")
    price_id = STRIPE_PRICE_YEARLY if plan == "yearly" else STRIPE_PRICE_MONTHLY

    if not price_id:
        return jsonify({"error": "Price not configured"}), 503

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{FRONTEND_URL}?upgraded=1",
            cancel_url=f"{FRONTEND_URL}?cancelled=1",
            client_reference_id=str(g.user.id),
            customer_email=g.user.email,
        )
        return jsonify({"url": session.url})
    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        return jsonify({"error": "Payment system error"}), 500


@app.route("/api/billing/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")

    if STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError):
            return jsonify({"error": "Invalid signature"}), 400
    else:
        event = json.loads(payload)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        if user_id:
            user = db.session.get(User, int(user_id))
            if user:
                user.plan = "premium"
                user.plan_expires = datetime.utcnow() + timedelta(days=365)
                user.stripe_customer_id = session.get("customer")
                db.session.commit()
                logger.info(f"User {user_id} upgraded to premium")

    elif event["type"] == "customer.subscription.deleted":
        customer_id = event["data"]["object"].get("customer")
        if customer_id:
            user = User.query.filter_by(stripe_customer_id=customer_id).first()
            if user:
                user.plan = "free"
                user.plan_expires = None
                db.session.commit()
                logger.info(f"User {user.id} subscription cancelled")

    return jsonify({"ok": True})


@app.route("/api/stats", methods=["GET"])
def public_stats():
    """Public stats for the landing page."""
    total_cases = ClassAction.query.count()
    active_cases = ClassAction.query.filter(ClassAction.status.in_(["Active", "Settlement Pending"])).count()
    total_users = User.query.count()
    total_checks = UserResult.query.count()
    return jsonify({
        "total_cases": total_cases,
        "active_cases": active_cases,
        "total_users": total_users,
        "total_checks": total_checks,
    })


# --- Admin: trigger auto-scraper ---
@app.route("/api/admin/scrape", methods=["POST"])
@login_required
def trigger_scrape():
    from auto_scraper import run_auto_scraper
    data = request.get_json() or {}
    sources = data.get("sources")  # Optional: list of source keys
    result = run_auto_scraper(sources)
    return jsonify(result)


@app.route("/api/admin/scrape-status", methods=["GET"])
@login_required
def scrape_status():
    from models import ScraperLog
    logs = ScraperLog.query.order_by(ScraperLog.created_at.desc()).limit(10).all()
    return jsonify({"logs": [l.to_dict() for l in logs]})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    debug = os.getenv("FLASK_ENV") == "development"
    logger.info(f"Starting Settlemate AU API on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
