from flask import Flask, request, Response
from yemot_flow import Flow
from yemot_ai import YemotAI, handle_yemot_hangup

app = Flask(__name__)
flow = Flow()

# יצירת מנהל AI
ai = YemotAI.create_codex_ai()  # או create_mock_ai() לבדיקות

@flow.get("5")
def ai_conversation(call):
    call_id = call.params.get("ApiCallId")
    user_text = call.params.get("RecordingText")
    
    if not user_text:
        call.play_message([("text", "דבר אחרי הצפצוף")])
        call.record(max_seconds=10, silence_timeout=3)
        return
    
    # קבלת תשובה מ-AI (ניהול סשן אוטומטי!)
    ai_response = ai.reply(call_id, user_text)
    
    # השמעת התשובה
    call.play_message([("text", ai_response)])
    call.record(max_seconds=10, silence_timeout=3)

@app.route("/yemot", methods=["POST"])
def yemot_handler():
    params = request.values.to_dict()
    xml = flow.handle_request(params)
    
    # ניקוי סשנים אוטומטי בסיום שיחה
    handle_yemot_hangup(ai, params)
    
    return Response(xml, mimetype="text/xml")

if __name__ == "__main__":
    app.run(debug=True)
