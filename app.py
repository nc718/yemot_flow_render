from flask import Flask, request, Response
from yemot_flow import Flow, Call

app = Flask(__name__)
flow = Flow(print_log=True)

@flow.get("8")
async def welcome(call: Call):
    """שיחה פשוטה עם 3 קלטים"""
    
    # קלט 1
    input1 = await call.read([('text', 'אנא הקש 1')], 
                            val_name="input1", max_digits=1, digits_allowed="1")
    
    # קלט 2 
    input2 = await call.read([('text', 'עכשיו הקש 2')], 
                            val_name="input2", max_digits=1, digits_allowed="2")
    
    # קלט 3
    input3 = await call.read([('text', 'ולסיום הקש 3')], 
                            val_name="input3", max_digits=1, digits_allowed="3")
    
    # סיכום
    call.play_message([('text', f'קלטת: {input1}, {input2}, {input3}. תודה!')])
    call.hangup()

@app.route("/yemot", methods=["GET", "POST"])
def yemot_entry():
    return Response(
        flow.handle_request(request.values.to_dict()),
        mimetype="text/plain; charset=utf-8"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
