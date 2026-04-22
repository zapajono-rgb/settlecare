"""
Settlemate AU - Populate database with class actions and eligibility questions.

Each case has specific yes/no questions that determine user eligibility.
Usage: python scraper.py
"""

import time
import logging
from datetime import datetime

from app import app
from models import db, ClassAction, EligibilityQuestion, ScraperLog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CASES = [
    {
        "case": {
            "case_name": "Thompson v Meta Platforms, Inc.",
            "file_number": "NSD 1234/2024",
            "defendant": "Meta Platforms, Inc.",
            "applicant": "Sarah Thompson",
            "court": "Federal Court of Australia",
            "status": "Settlement Pending",
            "description": (
                "Class action alleging Meta collected and used personal data of Australian "
                "Facebook users without adequate consent between 2015 and 2022. The case "
                "focuses on sharing user data with third-party applications and advertisers "
                "in breach of the Australian Privacy Act 1988. A proposed settlement of "
                "$50 million has been reached and is awaiting court approval."
            ),
            "eligibility_criteria": (
                "Australian residents who held a Facebook account between January 2015 and "
                "December 2022 whose data was shared with third-party apps without explicit consent."
            ),
            "claim_deadline": datetime(2025, 12, 31),
            "settlement_amount": "$50,000,000 AUD",
            "law_firm": "Maurice Blackburn Lawyers",
            "law_firm_contact": "1800 810 812",
            "law_firm_website": "https://www.mauriceblackburn.com.au",
            "claim_portal_url": "https://www.mauriceblackburn.com.au/class-actions/current/meta-facebook",
            "keywords": "facebook,meta,privacy,data,social media",
            "source_url": "https://www.fedcourt.gov.au/law-and-practice/class-actions",
        },
        "questions": [
            "Are you an Australian resident?",
            "Did you hold a Facebook account at any time between January 2015 and December 2022?",
            "Did you use Facebook features that connected to third-party apps (e.g. games, quizzes, 'Login with Facebook')?",
            "Were you unaware that your personal data was being shared with third-party advertisers or app developers?",
        ],
    },
    {
        "case": {
            "case_name": "Williams v Westpac Banking Corporation",
            "file_number": "VID 567/2024",
            "defendant": "Westpac Banking Corporation",
            "applicant": "James Williams",
            "court": "Federal Court of Australia",
            "status": "Active",
            "description": (
                "Class action against Westpac alleging systematic overcharging of fees on "
                "consumer and business transaction accounts between 2017 and 2023. Westpac "
                "charged fees for services not provided, duplicate transaction fees, and "
                "excessive dishonour fees in breach of Australian Consumer Law."
            ),
            "eligibility_criteria": (
                "Individuals or businesses with a Westpac transaction account between March 2017 "
                "and June 2023 who were charged duplicate fees, service fees for unused features, "
                "or excessive dishonour fees."
            ),
            "claim_deadline": datetime(2026, 6, 30),
            "settlement_amount": None,
            "law_firm": "Slater and Gordon",
            "law_firm_contact": "1800 555 777",
            "law_firm_website": "https://www.slatergordon.com.au",
            "claim_portal_url": "https://www.slatergordon.com.au/class-actions/current-class-actions/westpac-fees",
            "keywords": "westpac,bank,fees,overcharging,transaction,banking",
            "source_url": "https://www.fedcourt.gov.au/law-and-practice/class-actions",
        },
        "questions": [
            "Did you hold a Westpac transaction account (personal or business) between March 2017 and June 2023?",
            "Were you charged fees on your Westpac account during this period?",
            "Did you experience any of the following: duplicate transaction fees, fees for services you didn't use, or dishonour fees over $10?",
            "Are you an Australian resident or was the account held in Australia?",
        ],
    },
    {
        "case": {
            "case_name": "Liu v Telstra Corporation Limited",
            "file_number": "NSD 890/2024",
            "defendant": "Telstra Corporation Limited",
            "applicant": "Wei Liu",
            "court": "Federal Court of Australia",
            "status": "Active",
            "description": (
                "Class action alleging Telstra engaged in misleading conduct by advertising "
                "mobile network coverage and speeds that were not achievable. Customers in "
                "regional and suburban areas experienced persistent outages, significantly "
                "lower speeds than advertised, and were locked into contracts based on "
                "false coverage maps."
            ),
            "eligibility_criteria": (
                "Telstra mobile or broadband customers in regional or suburban Australia who "
                "experienced persistent outages or speeds below 50% of advertised rates "
                "between January 2020 and December 2023."
            ),
            "claim_deadline": None,
            "settlement_amount": None,
            "law_firm": "Shine Lawyers",
            "law_firm_contact": "1800 870 730",
            "law_firm_website": "https://www.shine.com.au",
            "claim_portal_url": "https://www.shine.com.au/class-actions/telstra-coverage",
            "keywords": "telstra,mobile,broadband,coverage,speed,outage",
            "source_url": "https://www.fedcourt.gov.au/law-and-practice/class-actions",
        },
        "questions": [
            "Were you a Telstra mobile or broadband customer between January 2020 and December 2023?",
            "Is/was your service address in a regional or suburban area of Australia?",
            "Did you experience persistent service outages or internet speeds significantly below what was advertised?",
            "Were you locked into a contract or plan based on Telstra's coverage map or speed claims?",
        ],
    },
    {
        "case": {
            "case_name": "Smith v Commonwealth Bank of Australia",
            "file_number": "VID 234/2023",
            "defendant": "Commonwealth Bank of Australia",
            "applicant": "David Smith",
            "court": "Federal Court of Australia",
            "status": "Settlement Approved",
            "description": (
                "Class action against CBA for charging financial advice fees to customers "
                "who received no advice — 'fees for no service'. Identified during the "
                "Royal Commission into Banking. The court approved a $120 million settlement."
            ),
            "eligibility_criteria": (
                "CBA customers charged ongoing financial advice fees between July 2010 and "
                "June 2019 who did not receive the corresponding advice services."
            ),
            "claim_deadline": datetime(2025, 9, 30),
            "settlement_amount": "$120,000,000 AUD",
            "law_firm": "Phi Finney McDonald",
            "law_firm_contact": "(03) 9134 7100",
            "law_firm_website": "https://www.phifinneymcdonald.com",
            "claim_portal_url": "https://www.phifinneymcdonald.com/current-claims/cba-fees-for-no-service",
            "keywords": "cba,commonwealth bank,fees,financial advice,royal commission",
            "source_url": "https://www.fedcourt.gov.au/law-and-practice/class-actions",
        },
        "questions": [
            "Were you a Commonwealth Bank customer between July 2010 and June 2019?",
            "Were you charged ongoing financial advice fees by CBA, Count Financial, or Commonwealth Financial Planning?",
            "Did you receive regular financial advice meetings or reviews corresponding to those fees?",
            "Are you an Australian resident?",
        ],
    },
    {
        "case": {
            "case_name": "Nguyen v Qantas Airways Limited",
            "file_number": "NSD 456/2024",
            "defendant": "Qantas Airways Limited",
            "applicant": "Thi Nguyen",
            "court": "Federal Court of Australia",
            "status": "Active",
            "description": (
                "Class action against Qantas for selling tickets on already-cancelled flights "
                "('ghost flights'). The ACCC found Qantas sold tickets for thousands of "
                "flights it had decided to cancel, and delayed notifying ticket holders."
            ),
            "eligibility_criteria": (
                "Consumers who purchased Qantas tickets between May 2021 and July 2023 for "
                "flights that were subsequently cancelled where Qantas had already decided "
                "to cancel before or shortly after selling the ticket."
            ),
            "claim_deadline": datetime(2026, 3, 31),
            "settlement_amount": None,
            "law_firm": "Echo Law",
            "law_firm_contact": "(02) 8599 2997",
            "law_firm_website": "https://www.echolaw.com.au",
            "claim_portal_url": "https://www.echolaw.com.au/qantas-ghost-flights",
            "keywords": "qantas,airline,flights,cancelled,ghost flights,travel",
            "source_url": "https://www.fedcourt.gov.au/law-and-practice/class-actions",
        },
        "questions": [
            "Did you purchase a Qantas flight ticket between May 2021 and July 2023?",
            "Was your flight subsequently cancelled by Qantas?",
            "Were you notified of the cancellation less than 48 hours before departure, or after you had already arrived at the airport?",
            "Did the cancellation cause you financial loss (e.g. accommodation, alternative transport, missed events)?",
        ],
    },
    {
        "case": {
            "case_name": "Park v Optus Networks Pty Ltd",
            "file_number": "NSD 789/2024",
            "defendant": "Optus Networks Pty Ltd",
            "applicant": "Min-Jun Park",
            "court": "Federal Court of Australia",
            "status": "Active",
            "description": (
                "Class action arising from the September 2022 Optus data breach, which "
                "exposed personal information of up to 9.8 million customers including "
                "passport numbers, driver licences, and Medicare details."
            ),
            "eligibility_criteria": (
                "Current or former Optus customers whose personal information was compromised "
                "in the September 2022 data breach."
            ),
            "claim_deadline": None,
            "settlement_amount": None,
            "law_firm": "Slater and Gordon",
            "law_firm_contact": "1800 555 777",
            "law_firm_website": "https://www.slatergordon.com.au",
            "claim_portal_url": "https://www.slatergordon.com.au/class-actions/current-class-actions/optus-data-breach",
            "keywords": "optus,data breach,privacy,cybersecurity,hack",
            "source_url": "https://www.fedcourt.gov.au/law-and-practice/class-actions",
        },
        "questions": [
            "Were you an Optus customer (mobile, broadband, or any service) in or before September 2022?",
            "Were you notified by Optus that your data was compromised in the breach?",
            "Was any of your identity documentation exposed (passport, driver licence, or Medicare number)?",
            "Did you experience any negative consequences (identity fraud, need to replace documents, stress/anxiety)?",
        ],
    },
    {
        "case": {
            "case_name": "Chen v Medibank Private Limited",
            "file_number": "VID 1012/2023",
            "defendant": "Medibank Private Limited",
            "applicant": "Li Chen",
            "court": "Federal Court of Australia",
            "status": "Active",
            "description": (
                "Class action following the October 2022 Medibank data breach that exposed "
                "sensitive health and personal data of 9.7 million current and former "
                "customers. Hackers accessed names, dates of birth, Medicare numbers, and "
                "health claims data including sensitive medical procedures."
            ),
            "eligibility_criteria": (
                "Current or former Medibank or ahm customers whose personal or health data "
                "was exposed in the October 2022 cyber attack."
            ),
            "claim_deadline": None,
            "settlement_amount": None,
            "law_firm": "Baker McKenzie",
            "law_firm_contact": "(02) 9225 0200",
            "law_firm_website": "https://www.bakermckenzie.com",
            "claim_portal_url": "https://www.bakermckenzie.com/en/insight/publications/2023/medibank-class-action",
            "keywords": "medibank,ahm,health insurance,data breach,privacy,medical",
            "source_url": "https://www.fedcourt.gov.au/law-and-practice/class-actions",
        },
        "questions": [
            "Were you a Medibank or ahm health insurance customer in or before October 2022?",
            "Were you notified by Medibank that your data was involved in the cyber attack?",
            "Was your personal information (name, DOB, Medicare number) or health claims data exposed?",
            "Have you experienced distress, identity fraud risks, or had to take protective action as a result?",
        ],
    },
    {
        "case": {
            "case_name": "Morrison v AMP Limited",
            "file_number": "NSD 345/2023",
            "defendant": "AMP Limited",
            "applicant": "Karen Morrison",
            "court": "Federal Court of Australia",
            "status": "Settlement Pending",
            "description": (
                "Class action against AMP for systemic failures in superannuation fund "
                "management, including charging members for insurance they didn't need, "
                "failing to consolidate duplicate accounts, and retaining members in "
                "underperforming funds when better options were available."
            ),
            "eligibility_criteria": (
                "AMP superannuation members between 2012 and 2022 who held duplicate accounts, "
                "were charged for default insurance without consent, or were kept in funds "
                "that consistently underperformed their benchmark."
            ),
            "claim_deadline": datetime(2026, 8, 31),
            "settlement_amount": "$95,000,000 AUD",
            "law_firm": "Quinn Emanuel",
            "law_firm_contact": "(02) 9146 3500",
            "law_firm_website": "https://www.quinnemanuel.com",
            "claim_portal_url": "https://www.quinnemanuel.com/amp-super-class-action",
            "keywords": "amp,superannuation,super,insurance,fees,retirement",
            "source_url": "https://www.fedcourt.gov.au/law-and-practice/class-actions",
        },
        "questions": [
            "Were you a member of an AMP superannuation fund between 2012 and 2022?",
            "Did you hold more than one AMP super account at the same time?",
            "Were you automatically enrolled in insurance through your AMP super without specifically requesting it?",
            "Do you believe your AMP super fund consistently underperformed compared to similar funds?",
        ],
    },
    {
        "case": {
            "case_name": "Taylor v Woolworths Group Limited",
            "file_number": "NSD 678/2024",
            "defendant": "Woolworths Group Limited",
            "applicant": "Emily Taylor",
            "court": "Federal Court of Australia",
            "status": "Active",
            "description": (
                "Class action alleging Woolworths systematically underpaid salaried store "
                "managers and assistant managers by failing to properly account for overtime, "
                "penalty rates, and public holiday entitlements under the General Retail "
                "Industry Award."
            ),
            "eligibility_criteria": (
                "Current or former Woolworths salaried store managers or assistant managers "
                "employed between January 2014 and December 2023 who regularly worked beyond "
                "their contracted hours."
            ),
            "claim_deadline": datetime(2026, 12, 31),
            "settlement_amount": None,
            "law_firm": "Adero Law",
            "law_firm_contact": "(07) 3088 7937",
            "law_firm_website": "https://www.aderolaw.com.au",
            "claim_portal_url": "https://www.aderolaw.com.au/class-actions/woolworths",
            "keywords": "woolworths,underpayment,wages,overtime,retail,employment",
            "source_url": "https://www.fedcourt.gov.au/law-and-practice/class-actions",
        },
        "questions": [
            "Were you employed by Woolworths as a salaried store manager or assistant manager?",
            "Were you employed in this role at any time between January 2014 and December 2023?",
            "Did you regularly work hours beyond your contracted 38-hour week (e.g. early starts, late finishes, weekend work)?",
            "Were you paid a flat salary without separate overtime or penalty rate payments for those extra hours?",
        ],
    },
    {
        "case": {
            "case_name": "Reeves v Toyota Motor Corporation Australia",
            "file_number": "VID 901/2024",
            "defendant": "Toyota Motor Corporation Australia",
            "applicant": "Mark Reeves",
            "court": "Federal Court of Australia",
            "status": "Active",
            "description": (
                "Class action alleging defective diesel particulate filter (DPF) systems "
                "in Toyota HiLux, Fortuner, and Prado vehicles manufactured between 2015 "
                "and 2020. Owners report repeated DPF warning lights, forced regeneration "
                "cycles, reduced performance, and costly repairs not covered by warranty."
            ),
            "eligibility_criteria": (
                "Owners of Toyota HiLux, Fortuner, or Prado diesel vehicles manufactured "
                "between 2015 and 2020 who have experienced DPF-related issues."
            ),
            "claim_deadline": None,
            "settlement_amount": None,
            "law_firm": "Bannister Law",
            "law_firm_contact": "1800 011 581",
            "law_firm_website": "https://www.bannisterlaw.com.au",
            "claim_portal_url": "https://www.bannisterlaw.com.au/class-actions/toyota-dpf",
            "keywords": "toyota,hilux,prado,fortuner,diesel,dpf,vehicle,car,defect",
            "source_url": "https://www.fedcourt.gov.au/law-and-practice/class-actions",
        },
        "questions": [
            "Do you own or have you owned a Toyota HiLux, Fortuner, or Prado diesel vehicle manufactured between 2015 and 2020?",
            "Have you experienced DPF (diesel particulate filter) warning lights or forced regeneration issues?",
            "Have you paid for DPF-related repairs or experienced reduced vehicle performance due to DPF problems?",
            "Is the vehicle registered in Australia?",
        ],
    },
]


def run_scraper():
    start = time.time()

    with app.app_context():
        db.create_all()

        added = 0
        updated = 0

        for entry in CASES:
            case_data = entry["case"]
            questions = entry["questions"]

            existing = ClassAction.query.filter_by(
                file_number=case_data["file_number"]
            ).first()

            if existing:
                for key, value in case_data.items():
                    if value is not None:
                        setattr(existing, key, value)
                case_obj = existing
                updated += 1
            else:
                case_obj = ClassAction(**case_data)
                db.session.add(case_obj)
                db.session.flush()  # Get the ID
                added += 1

            # Upsert questions
            existing_qs = EligibilityQuestion.query.filter_by(
                class_action_id=case_obj.id
            ).all()

            if not existing_qs:
                for i, q_text in enumerate(questions):
                    q = EligibilityQuestion(
                        class_action_id=case_obj.id,
                        question_text=q_text,
                        question_order=i,
                        # For Q3 on CBA case: "Did you receive advice?" -> must answer No
                        required_answer=(
                            False if case_obj.file_number == "VID 234/2023" and i == 2
                            else True
                        ),
                    )
                    db.session.add(q)

        db.session.commit()
        duration = time.time() - start

        log = ScraperLog(
            source="demo_data_v2",
            status="success",
            cases_found=len(CASES),
            cases_added=added,
            cases_updated=updated,
            duration_seconds=round(duration, 2),
        )
        db.session.add(log)
        db.session.commit()

        total = ClassAction.query.count()
        total_q = EligibilityQuestion.query.count()
        logger.info(f"Done: {added} added, {updated} updated ({duration:.2f}s)")
        logger.info(f"Database: {total} cases, {total_q} eligibility questions")


if __name__ == "__main__":
    run_scraper()
