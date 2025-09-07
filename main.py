from flask import Flask, render_template, request, redirect
from src.service.ledger import Ledger
from waitress import serve
from configs import EndpointConfigs
from typing import List, Dict
from src.utils.logger import logger
from collections import defaultdict

EPSILON = 1e-9  # Threshold for floating point comparison


app = Flask(__name__)
app.secret_key = EndpointConfigs.app_key
ledger = Ledger()
HOME_PATH = "/home"


# pyright: ignore[reportGeneralTypeIssues]
def generate_summary(ledger: List[Dict[str, any]]) -> List[Dict[str, any]]:
    data_dict = {}
    for data in ledger:
        original_key = data["by"]+"->"+data["to"]
        reverse_key = data["to"]+"->"+data["by"]
        if reverse_key in data_dict:
            data_dict[original_key] = data_dict.get(
                original_key, 0) + data["amount"] - data_dict[reverse_key]
            if data_dict[original_key] < 0:
                data_dict[reverse_key] = data_dict[original_key]*-1
                del data_dict[original_key]
            else:
                del data_dict[reverse_key]
        else:
            data_dict[original_key] = data_dict.get(
                original_key, 0) + data["amount"]
    result = []
    for (key, value) in data_dict.items():
        by, to = key.split("->")
        result.append({"by": by, "to": to, "amount": round(value, 2)})
    result.sort(key=lambda x: x["to"])
    return result


def simplify(transactions):
    """
    Simplifies a list of transactions by calculating net balances for each user and generating a minimal set of payments to settle all debts.

    Args:
        transactions (list of dict): Each transaction dict should have 'by', 'to', and 'amount' keys.

    Returns:
        list of dict: Each dict represents a simplified transaction with the following structure:
            {
                'by': <creditor_name: str>,
                'to': <debtor_name: str>,
                'amount': <amount_to_settle: float>
            }
    """
    net_balances = defaultdict(float)

    debtors = []
    creditors = []

    for t in transactions:
        amount = round(t['amount'], 1)
        net_balances[t['to']] -= amount
        net_balances[t['by']] += amount

    for user, balance in net_balances.items():
        if balance < 0:
            debtors.append((user, -balance))
        elif balance > 0:
            creditors.append((user, balance))

    # Sort debtors and creditors by largest balance to optimize settlement order.
    debtors.sort(key=lambda x: -x[1])
    creditors.sort(key=lambda x: -x[1])

    simplified = []
    d_idx = 0
    c_idx = 0

    while d_idx < len(debtors) and c_idx < len(creditors):
        curr_debtor, debt_amt = debtors[d_idx]
        curr_creditor, credit_amt = creditors[c_idx]

        settle_amt = min(debt_amt, credit_amt)
        simplified.append({
            'to': curr_debtor,
            'by': curr_creditor,
            'amount': settle_amt
        })

        debt_amt -= settle_amt
        credit_amt -= settle_amt
        if debt_amt < EPSILON:
            d_idx += 1
        else:
            debtors[d_idx] = (curr_debtor, debt_amt)

        if credit_amt < EPSILON:
            c_idx += 1
        else:
            creditors[c_idx] = (curr_creditor, credit_amt)

    return simplified


# pyright: ignore[reportGeneralTypeIssues]
def get_summary(group_id, group_details, wants_simplified) -> tuple[bool, List[Dict[str, any]]]:
    if wants_simplified:
        if "simplified" in group_details:
            return True, group_details["simplified"]
        else:
            summary = simplify(group_details["summary"])
            ledger.simplify_archive_group(
                group_id=group_id, summary=summary)
            return True, summary
    return False, group_details["summary"]


@app.route("/")
@app.route("/index")
@app.route(HOME_PATH)
def home():
    group_url = request.args.get("group_url")
    return render_template(template_name_or_list="index.html", group_url=group_url)


@app.route("/group", methods=["GET"])
def group_page():
    try:
        group_id = request.args.get("groupId")
        if not group_id or not isinstance(group_id, str):
            logger.error("Invalid or missing group ID")
            return redirect(HOME_PATH)

        logger.info(f"Group target request received for group id: {group_id}")
        group_details = ledger.get_group_details(group_id=group_id)

        if group_details is None:
            logger.warning(f"Group not found for ID: {group_id}")
            return redirect(HOME_PATH)

        logger.info(f"Loading group id: {group_id}")
        return render_template(
            template_name_or_list="group.html",
            group_id=group_id,
            group_name=group_details["name"],
            group_members=",".join(group_details["members"]),
            ledger=group_details["ledger"],
            group_description=group_details["description"]
        )
    except Exception as e:
        logger.error(f"Error loading group page: {str(e)}")
        return redirect(HOME_PATH)


@app.route("/create-group", methods=["POST"])
def create_group():
    group_name = request.form.get("groupName", "")
    group_members = [name.strip()
                     for name in request.form.get("names", "").split(",")]
    group_description = request.form.get(
        "groupDescription") if request.form.get("groupDescription") else None
    logger.info(
        f"Create group request received with the group name as {group_name}.")
    group_id = ledger.create_group(
        group_name=group_name, group_members=group_members, description=group_description)
    group_url = request.url.rsplit("/", 1)[0]+"/group?groupId="+group_id
    logger.info(f"Group successfully created for {group_name}")
    return render_template(template_name_or_list="index.html", group_url=group_url)


@app.route("/create-record", methods=["POST"])
def create_record_function():
    group_id = request.form.get("group_id", "")
    split_equal = True if request.form.get(
        "is_split_equally") == 'true' else False
    logger.info(
        f"Received request to create an {'equal split' if split_equal else 'unequal split'} record for group with Id = {group_id}.")
    if split_equal:
        paid_by = request.form.get("paid_by", "")
        to = request.form.getlist("split_by[]")
        amount = request.form.get("amount", "")
        description = request.form.get("description", "")
        logger.info(f"Equal split record created successfully for {group_id}")
    else:
        paid_by = request.form.getlist('expense_by')
        to = request.form.getlist('expense_to')
        amount = request.form.getlist('expense_amount')
        description = request.form.getlist('expense_description')
        logger.info(
            f"Unequal split record created successfully for {group_id}")
    ledger.insert_to_ledger(group_id, paid_by, amount,  # pyright: ignore[reportArgumentType]
                            to, description, split_equal)
    return redirect("/group?groupId={}".format(group_id))


@app.route("/summarize", methods=["GET"])
def summarize_transactions():
    is_archive = False
    is_simple = False
    archive_group_id = None
    wants_simplified = False
    if request.args.get("archiveGroupId"):
        is_archive = True
        group_id = request.args.get("archiveGroupId", "")
        archive_group_id = group_id
        wants_simplified = True if "simple" in request.args and request.args.get(
            "simple") == "true" else False
    else:
        group_id = request.args.get("groupId", "")
    logger.info(
        f"Summarize request received for {'an archive group' if is_archive else 'a group'} with Id: {group_id}")
    group_details = ledger.get_group_details(
        group_id=group_id, archive=is_archive)
    if group_details is None:
        return redirect(HOME_PATH)
    summary_url = None
    valid_till = None
    is_simple = group_details["is_simplified"]
    if not is_archive:
        summary = generate_summary(group_details["ledger"])
        archive_group_id = ledger.archive_group(
            group_id=group_id, summary=summary)
        summary_url = request.url.rsplit(
            "/", 1)[0]+"/summarize?archiveGroupId="+archive_group_id
        logger.info(
            f"Summarized successfully for {group_details['name']}({group_id})!")
    else:
        is_simple, summary = get_summary(
            group_id=group_id, group_details=group_details, wants_simplified=wants_simplified)
        valid_till = group_details["valid_till"]
        logger.info(
            f"Archived summary of {group_details['name']}({group_id}) was presented!")
    return render_template(
        template_name_or_list="summary.html",
        group_id=archive_group_id,
        group_name=group_details["name"],
        simple=is_simple,
        summary=summary,
        summary_url=summary_url,
        valid_till=valid_till
    )


@app.route("/ping")
@app.route("/health")
def health():
    return "OK"


if __name__ == "__main__":
    serve(app=app, host=EndpointConfigs.host, port=EndpointConfigs.port)
