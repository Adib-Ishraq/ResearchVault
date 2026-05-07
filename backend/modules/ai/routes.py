from flask import Blueprint, request, jsonify, current_app
from groq import Groq

from middleware.session import require_auth

ai_bp = Blueprint("ai", __name__)

_SYSTEM_PROMPT = """\
You are an AI research assistant embedded in Research Vault, an academic collaboration platform for researchers, supervisors, postgraduate students, and undergraduates.

You help users with:
- Research methodology and study design
- Literature review strategies and structuring arguments
- Academic writing, abstracts, and paper structuring
- Statistical concepts and data analysis advice
- Reviewing and improving research proposals
- Finding relevant research directions within a given domain
- Navigating the Research Vault platform (rooms, profiles, publications, direct messaging)

Guidelines:
- Be concise and to the point; prefer short paragraphs or bullet lists over long prose.
- Use markdown formatting (bold, lists, code blocks) when it aids clarity.
- Never fabricate paper titles, authors, DOIs, or citations.
- If a question is outside research or the platform, politely redirect the user.\
"""


@ai_bp.post("/chat")
@require_auth
def chat():
    data = request.get_json(force=True)
    message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400

    api_key = current_app.config.get("GROQ_API_KEY", "")
    if not api_key:
        return jsonify({"error": "AI assistant is not configured on this server"}), 503

    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for turn in history[-20:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": message})

    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1024,
    )

    return jsonify({"response": resp.choices[0].message.content}), 200
