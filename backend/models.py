import json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(300), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quiz_completed = db.Column(db.Boolean, default=False)

    # Premium subscription
    plan = db.Column(db.String(20), default="free")  # "free", "premium"
    plan_expires = db.Column(db.DateTime, nullable=True)
    stripe_customer_id = db.Column(db.String(200), nullable=True)
    checks_used = db.Column(db.Integer, default=0)  # Free tier limit tracking

    results = db.relationship("UserResult", backref="user", lazy=True)

    FREE_CHECK_LIMIT = 3

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_premium(self):
        if self.plan != "premium":
            return False
        if self.plan_expires and self.plan_expires < datetime.utcnow():
            return False
        return True

    @property
    def can_check(self):
        if self.is_premium:
            return True
        return self.checks_used < self.FREE_CHECK_LIMIT

    @property
    def checks_remaining(self):
        if self.is_premium:
            return -1  # unlimited
        return max(0, self.FREE_CHECK_LIMIT - self.checks_used)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "quiz_completed": self.quiz_completed,
            "plan": self.plan,
            "is_premium": self.is_premium,
            "checks_remaining": self.checks_remaining,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ClassAction(db.Model):
    __tablename__ = "class_actions"

    id = db.Column(db.Integer, primary_key=True)
    case_name = db.Column(db.String(500), nullable=False)
    file_number = db.Column(db.String(100), unique=True, nullable=False)
    defendant = db.Column(db.String(300), nullable=False, index=True)
    applicant = db.Column(db.String(300))
    court = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text)
    eligibility_criteria = db.Column(db.Text)
    claim_deadline = db.Column(db.DateTime, index=True)
    settlement_amount = db.Column(db.String(100))
    law_firm = db.Column(db.String(300))
    law_firm_contact = db.Column(db.String(300))
    law_firm_website = db.Column(db.String(500))
    claim_portal_url = db.Column(db.String(500))
    keywords = db.Column(db.Text)
    source_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    questions = db.relationship("EligibilityQuestion", backref="class_action", lazy=True,
                                order_by="EligibilityQuestion.question_order")

    @classmethod
    def search(cls, query):
        pattern = f"%{query}%"
        return cls.query.filter(
            db.or_(
                cls.case_name.ilike(pattern),
                cls.defendant.ilike(pattern),
                cls.description.ilike(pattern),
                cls.keywords.ilike(pattern),
            )
        )

    @classmethod
    def get_active(cls):
        return cls.query.filter(cls.status.in_(["Active", "Settlement Pending"]))

    def to_dict(self, include_questions=False):
        d = {
            "id": self.id,
            "case_name": self.case_name,
            "file_number": self.file_number,
            "defendant": self.defendant,
            "applicant": self.applicant,
            "court": self.court,
            "status": self.status,
            "description": self.description,
            "eligibility_criteria": self.eligibility_criteria,
            "claim_deadline": self.claim_deadline.isoformat() if self.claim_deadline else None,
            "settlement_amount": self.settlement_amount,
            "law_firm": self.law_firm,
            "law_firm_contact": self.law_firm_contact,
            "law_firm_website": self.law_firm_website,
            "claim_portal_url": self.claim_portal_url,
            "source_url": self.source_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_questions:
            d["questions"] = [q.to_dict() for q in self.questions]
        return d


class EligibilityQuestion(db.Model):
    __tablename__ = "eligibility_questions"

    id = db.Column(db.Integer, primary_key=True)
    class_action_id = db.Column(db.Integer, db.ForeignKey("class_actions.id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_order = db.Column(db.Integer, default=0)
    # True = user must answer Yes to this question to be eligible
    required_answer = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "question_text": self.question_text,
            "question_order": self.question_order,
            "required_answer": self.required_answer,
        }


class UserResult(db.Model):
    __tablename__ = "user_results"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    class_action_id = db.Column(db.Integer, db.ForeignKey("class_actions.id"), nullable=False)
    is_eligible = db.Column(db.Boolean, nullable=False)
    answers_json = db.Column(db.Text)  # JSON: [{question_id, answer}]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class_action = db.relationship("ClassAction")

    __table_args__ = (
        db.UniqueConstraint("user_id", "class_action_id", name="uq_user_case"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "class_action_id": self.class_action_id,
            "is_eligible": self.is_eligible,
            "answers": json.loads(self.answers_json) if self.answers_json else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "case": self.class_action.to_dict() if self.class_action else None,
        }


class QuizAnswer(db.Model):
    __tablename__ = "quiz_answers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    class_action_id = db.Column(db.Integer, db.ForeignKey("class_actions.id"), nullable=False)
    answer = db.Column(db.String(20), nullable=False)  # "yes", "no", "not_sure"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "class_action_id", name="uq_quiz_answer"),
    )


class UserArchive(db.Model):
    __tablename__ = "user_archives"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    class_action_id = db.Column(db.Integer, db.ForeignKey("class_actions.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "class_action_id", name="uq_user_archive"),
    )


class ScraperLog(db.Model):
    __tablename__ = "scraper_logs"

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    cases_found = db.Column(db.Integer, default=0)
    cases_added = db.Column(db.Integer, default=0)
    cases_updated = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    duration_seconds = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "status": self.status,
            "cases_found": self.cases_found,
            "cases_added": self.cases_added,
            "cases_updated": self.cases_updated,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
