from flask import Flask, request, Response
from yemot_flow import Flow, Call

app = Flask(__name__)
flow = Flow(print_log=True)

@flow.get("5")
async def speech_demo(call: Call):
    name = await call.read([('text', 'אמור את שמך')], 
                          mode="stt", val_name="name", lang="he-IL")
    
    call.play_message([('text', f'שלום {name}, נעים להכיר!')])
    call.hangup()
    
@app.route("/yemot", methods=["GET", "POST"])
def yemot_entry():
    return Response(
        flow.handle_request(request.values.to_dict()),
        mimetype="text/plain; charset=utf-8"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
