from flask import Flask, render_template, request, redirect
from src.service.ledger import Ledger
from waitress import serve
from configs import EndpointConfigs
from typing import List, Dict


app = Flask(__name__)
app.secret_key = EndpointConfigs.app_key
ledger = Ledger()


def generate_summary(ledger: List[Dict[str, any]]) -> List[Dict[str, any]]:
    data_dict = {}
    for data in ledger:
        original_key = data["by"]+"->"+data["to"]
        reverse_key = data["to"]+"->"+data["by"]
        if reverse_key in data_dict:
            data_dict[original_key] = data_dict.get(original_key, 0) + data["amount"] - data_dict[reverse_key]
            if data_dict[original_key]<0:
                data_dict[reverse_key] = data_dict[original_key]*-1
                del data_dict[original_key]
            else:
                del data_dict[reverse_key]
        else:
            data_dict[original_key] = data_dict.get(original_key, 0) + data["amount"]
    result = []
    for (key, value) in data_dict.items():
        by, to = key.split("->")
        result.append({"by": by, "to": to, "amount": value})
    return result


@app.route("/")
@app.route("/index")
@app.route("/home")
def home():
    group_url = request.args.get("group_url")
    return render_template(template_name_or_list="index.html", group_url=group_url)


@app.route("/group", methods=["GET"])
def group_page():
    group_id = request.args.get("groupId")
    if group_id is None:
        return redirect("/home")
    group_details = ledger.get_group_details(group_id=group_id)
    if group_details is None:
        return redirect("/home")
    return render_template(
        template_name_or_list="group.html",
        group_id=group_id,
        group_name=group_details["name"],
        group_members=",".join(group_details["members"]),
        ledger=group_details["ledger"],
        group_description=group_details["description"]
    )


@app.route("/create-group", methods=["POST"])
def create_group():
    group_name = request.form.get("groupName")
    group_members = [name.strip()
                     for name in request.form.get("names").split(",")]
    group_description = request.form.get(
        "groupDescription") if request.form.get("groupDescription") else None
    group_id = ledger.create_group(
        group_name=group_name, group_members=group_members, description=group_description)
    group_url = request.url.rsplit("/", 1)[0]+"/group?groupId="+group_id
    return render_template(template_name_or_list="index.html", group_url=group_url)


@app.route("/create-record", methods=["POST"])
def create_record_function():
    group_id = request.form.get("group_id")
    split_equal = True if request.form.get("is_split_equally")=='true' else False
    if split_equal:
        paid_by = request.form.get("paid_by")
        to = [name.strip() for name in request.form.get("split_by").split(",")]
        amount = request.form.get("amount", type=float)
        description = request.form.get("description")
    else:
        paid_by = request.form.getlist('expense_by')
        to = request.form.getlist('expense_to')
        amount = request.form.getlist('expense_amount')
        description = request.form.getlist('expense_description')
    ledger.insert_to_ledger(group_id, paid_by, amount,
                            to, description, split_equal)
    return redirect("/group?groupId={}".format(group_id))


@app.route("/summarize", methods=["GET"])
def summarize_transactions():
    is_archive = False
    if request.args.get("archiveGroupId"):
        is_archive = True
        group_id = request.args.get("archiveGroupId")
    else:
        group_id = request.args.get("groupId")
    group_details = ledger.get_group_details(group_id=group_id, archive=is_archive)
    summary_url = None
    valid_till = None
    if not is_archive:
        summary = generate_summary(group_details["ledger"])
        archive_id = ledger.archive_group(group_id=group_id, summary=summary)
        summary_url = request.url.rsplit("/", 1)[0]+"/summarize?archiveGroupId="+archive_id
    else:
        summary = group_details["summary"]
        valid_till = group_details["valid_till"]
    return render_template(
        template_name_or_list="summary.html",
        group_name=group_details["name"],
        summary=summary,
        summary_url=summary_url,
        valid_till=valid_till
    )


if __name__ == "__main__":
    serve(app=app, host=EndpointConfigs.host, port=EndpointConfigs.port)
