import streamlit as st
import api_client

st.set_page_config(page_title="Chat", page_icon="💬", layout="wide")
st.title("💬 Ask the report")

# session_state keeps the chat history between reruns
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Ask me anything about the report.", "citations": []}
    ]


def show(m):
    with st.chat_message(m["role"]):
        st.write(m["content"])
        if m["citations"]:
            with st.expander("Sources"):
                for c in m["citations"]:
                    st.caption(f"[{c['id']}] p.{c['page']}: “{c['quote']}”")


for m in st.session_state.messages:
    show(m)

question = st.chat_input("Ask a question about the report...")
if question:
    user_msg = {"role": "user", "content": question, "citations": []}
    st.session_state.messages.append(user_msg)
    show(user_msg)
    reply = api_client.ask_question(question, st.session_state.messages)
    bot_msg = {"role": "assistant", "content": reply["answer"], "citations": reply["citations"]}
    st.session_state.messages.append(bot_msg)
    show(bot_msg)