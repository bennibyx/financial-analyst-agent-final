
"""Document-grounded chat with saved conversations and citations."""

import streamlit as st

import api_client


st.set_page_config(
    page_title="Financial Analyst Agent — Chat",
    page_icon="💬",
    layout="wide",
)

st.title("💬 Ask the report")
st.write(
    "Ask questions about your uploaded document. "
    "Answers come from the backend analyst agent and may include "
    "supporting quotes from the document."
)

# Prefer the document whose analysis was most recently completed.
document_id = st.session_state.get("analysis_document_id")

if document_id is None:
    document_id = st.session_state.get("document_id")

if document_id is None:
    st.info(
        "Upload a document on the Upload page first, then return here "
        "to ask questions about it."
    )
    st.stop()

st.caption(f"Selected document ID: {document_id}")

# Track which document the current conversation belongs to.
active_document = st.session_state.get("chat_document_id")

if str(active_document) != str(document_id):
    st.session_state["chat_document_id"] = document_id
    st.session_state["chat_conversation_id"] = None
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": (
                "Your document is selected. Ask me a question about "
                "its contents, financial results, risks, or outlook."
            ),
            "citations": [],
            "issues": [],
        }
    ]


def show_message(message):
    """Render one chat message and its supporting citations."""
    with st.chat_message(message["role"]):
        st.write(message["content"])

        citations = message.get("citations") or []

        if citations:
            with st.expander(f"Sources ({len(citations)})"):
                for index, citation in enumerate(citations, start=1):
                    quote = citation.get("quote", "")
                    cited_doc = citation.get("doc_id", str(document_id))

                    st.caption(f"[{index}] Document {cited_doc}")
                    st.write(f"> {quote}")

        if message.get("answered") is False:
            st.caption(
                "The agent could not verify an answer from the document "
                "with supporting citations."
            )

        issues = message.get("issues") or []

        if issues:
            with st.expander("Verification notes"):
                for issue in issues:
                    st.write(f"- {issue}")


if st.button("Start a new conversation"):
    st.session_state["chat_conversation_id"] = None
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": "New conversation started. What would you like to know?",
            "citations": [],
            "issues": [],
        }
    ]
    st.rerun()


messages = st.session_state.setdefault(
    "messages",
    [
        {
            "role": "assistant",
            "content": "What would you like to know about this document?",
            "citations": [],
            "issues": [],
        }
    ],
)

for message in messages:
    show_message(message)


question = st.chat_input("Ask a question about the uploaded document...")

if question and question.strip():
    user_message = {
        "role": "user",
        "content": question.strip(),
        "citations": [],
        "issues": [],
    }
    messages.append(user_message)

    # Show the question immediately.
    show_message(user_message)

    try:
        with st.chat_message("assistant"):
            with st.spinner(
                "Searching the document and preparing an evidence-based answer..."
            ):
                reply = api_client.ask_question(
                    question=question.strip(),
                    document_id=document_id,
                    conversation_id=st.session_state.get(
                        "chat_conversation_id"
                    ),
                )

        conversation_id = reply.get("conversation_id")

        if conversation_id is not None:
            st.session_state["chat_conversation_id"] = conversation_id

        assistant_message = {
            "role": "assistant",
            "content": reply.get("answer") or (
                "The analyst did not return an answer."
            ),
            "citations": reply.get("citations") or [],
            "answered": reply.get("answered", False),
            "issues": reply.get("issues") or [],
        }

        messages.append(assistant_message)
        st.rerun()

    except Exception as exc:
        error_message = {
            "role": "assistant",
            "content": f"Chat request failed: {exc}",
            "citations": [],
            "issues": [],
        }
        messages.append(error_message)
        st.rerun()
