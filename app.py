from flask import Flask, request, Response
from yemot_flow import Flow, Call
from yemot_ai import AI
import os

app = Flask(__name__)
flow = Flow(print_log=True)

# יצירת מנהל AI עם Gemini
ai = AI.create_gemini_ai(
    api_key=os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY"),
    model="gemini-pro"
)

@flow.get("")
async def welcome(call: Call):
    """שיחה עם AI"""
    call_id = call.params.get("ApiCallId")
    user_text = call.params.get("RecordingText")
    
    # אם אין טקסט מהמשתמש, מבקש הקלטה
    if not user_text:
        call.play_message([('text', 'דבר אחרי הצפצוף')])
        await call.record(max_seconds=10, silence_timeout=3)
        return
    
    # קבלת תשובה מ-AI
    ai_response = ai.reply(call_id, user_text)
    
    # השמעת התשובה
    call.play_message([('text', ai_response)])
    await call.record(max_seconds=10, silence_timeout=3)

@app.route("/yemot", methods=["GET", "POST"])
def yemot_entry():
    params = request.values.to_dict()
    
    # ניקוי סשן בסיום שיחה
    if params.get("hangup") == "yes":
        call_id = params.get("ApiCallId")
        if call_id:
            ai.end_conversation(call_id)
    
    return Response(
        flow.handle_request(params),
        mimetype="text/plain; charset=utf-8"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
