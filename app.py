"""The web page. Run with:  python -m streamlit run app.py
(The API must also be running:  python -m uvicorn main:app --reload)"""
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="AskMyData", page_icon="📊", layout="wide")


def call_api(method, path, **kwargs):
    """Talk to our API. Returns (data, error_message)."""
    try:
        response = requests.request(method, API_URL + path, timeout=90, **kwargs)
    except requests.exceptions.ConnectionError:
        return None, "Cannot reach the API. Is `python -m uvicorn main:app --reload` running?"
    if response.status_code == 200:
        return response.json(), None
    try:
        return None, response.json().get("detail", "Something went wrong")
    except ValueError:
        return None, "Something went wrong"


# ---------- remember things between clicks ----------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "dataset" not in st.session_state:
    st.session_state.dataset = None
if "loaded_file" not in st.session_state:
    st.session_state.loaded_file = None
if "just_loaded" not in st.session_state:
    st.session_state.just_loaded = False

if st.session_state.dataset is None:
    data, error = call_api("GET", "/dataset")
    if error:
        st.error(error)
        st.stop()
    st.session_state.dataset = data

# ---------- sidebar: choose the data ----------
with st.sidebar:
    st.header("📁 Your data")
    uploaded = st.file_uploader("Upload an Excel (.xlsx) or CSV file", type=["xlsx", "csv"])

    if uploaded is not None:
        file_id = f"{uploaded.name}-{uploaded.size}"
        if st.session_state.loaded_file != file_id:
            with st.spinner("Reading your file..."):
                data, error = call_api(
                    "POST", "/upload", files={"file": (uploaded.name, uploaded.getvalue())}
                )
            if error:
                st.error(error)
            else:
                st.session_state.dataset = data
                st.session_state.loaded_file = file_id
                st.session_state.just_loaded = True
                st.session_state.messages = []

    if st.button("Use the sample sales data"):
        data, error = call_api("POST", "/reset")
        if error:
            st.error(error)
        else:
            st.session_state.dataset = data
            st.session_state.loaded_file = None
            st.session_state.just_loaded = False
            st.session_state.messages = []
            st.rerun()

    st.caption(
        "Privacy: the free AI service may use what you send it. "
        "Do not upload private or confidential data."
    )

# ---------- main area ----------
st.title("📊 AskMyData")
st.write("Upload an Excel or CSV file, then ask questions about it in plain English.")

dataset = st.session_state.dataset

if dataset["source"] == "uploaded":
    if st.session_state.just_loaded:
        st.success("✅ File loaded! You can now ask questions about your data.")
    else:
        st.info("Using your uploaded file. Ask a question below.")
else:
    st.info("Using the built-in sample sales data. Upload your own file in the sidebar, or just ask a question.")

with st.expander("👀 See your data", expanded=st.session_state.just_loaded):
    for table in dataset["tables"]:
        st.markdown(f"**{table['table']}** — {table['rows']} rows")
        st.dataframe(table["preview"], use_container_width=True)
        st.caption("Columns: " + ", ".join(table["columns"]))

# ---------- chat ----------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message.get("sql"):
            with st.expander("SQL the AI wrote (always check it!)"):
                st.code(message["sql"], language="sql")
                st.write("Rows from the database:")
                st.dataframe(message["rows"])

question = st.chat_input("Ask a question about your data...")

if question:
    st.session_state.just_loaded = False
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            data, error = call_api("POST", "/ask", json={"question": question})
        if error:
            st.error(error)
            st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {error}"})
        else:
            st.write(data["answer"])
            if data["sql"]:
                with st.expander("SQL the AI wrote (always check it!)"):
                    st.code(data["sql"], language="sql")
                    st.write("Rows from the database:")
                    st.dataframe(data["rows"])
            st.session_state.messages.append(
                {"role": "assistant", "content": data["answer"], "sql": data["sql"], "rows": data["rows"]}
            )
