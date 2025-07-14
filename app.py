import streamlit as st

import streamlit as st
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings, HuggingFaceInstructEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from htmlTemplates import css, bot_template, user_template
from langchain.llms import HuggingFaceHub

def get_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text


def get_text_chunks(text):
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks


def get_vectorstore(text_chunks):
    embeddings = OpenAIEmbeddings()
    # embeddings = HuggingFaceInstructEmbeddings(model_name="hkunlp/instructor-xl")
    vectorstore = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
    return vectorstore


def get_conversation_chain(vectorstore):
    llm = ChatOpenAI()
    # llm = HuggingFaceHub(repo_id="google/flan-t5-xxl", model_kwargs={"temperature":0.5, "max_length":512})

    memory = ConversationBufferMemory(
        memory_key='chat_history', return_messages=True)
    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        memory=memory
    )
    return conversation_chain


def handle_userinput(user_question):
    response = st.session_state.conversation({'question': user_question})
    st.session_state.chat_history = response['chat_history']

    for i, message in enumerate(st.session_state.chat_history):
        if i % 2 == 0:
            st.write(user_template.replace(
                "{{MSG}}", message.content), unsafe_allow_html=True)
        else:
            st.write(bot_template.replace(
                "{{MSG}}", message.content), unsafe_allow_html=True)


def main():
    load_dotenv()
    st.set_page_config(page_title="Research Summarizer", layout="wide")
    with st.sidebar:
        st.subheader("Your documents")
        pdf_docs = st.file_uploader("Upload your Research Papers here and click on 'Enter'", accept_multiple_files=True)
        st.button("Enter")
        if st.button("Process"):
            with st.spinner("Processing"):
                # get pdf text
                raw_text = get_pdf_text(pdf_docs)

                # get the text chunks
                text_chunks = get_text_chunks(raw_text)

                # create vector store
                vectorstore = get_vectorstore(text_chunks)

                # create conversation chain
                st.session_state.conversation = get_conversation_chain(
                    vectorstore)

    # Title
    st.title("📚 Research Paper Summariser")

    # Dropdowns in 4 columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        customize_length = st.selectbox("📏 Summary Length", ["Short", "Medium", "Detailed"])
    with col2:
        summary_mode = st.selectbox("🛠️ Summary Mode", ["Extractive", "Abstractive"])
    with col3:
        section_choice = st.selectbox("📑 Section-wise Summary", ["Abstract", "Intro", "Method", "Conclusion", "References"])
    with col4:
        customize_percent = st.selectbox("Select Summary %", [f"{i}%" for i in range(10, 110, 10)])

    
    # Jargon Simplifier centered below the dropdowns
    st.markdown(
        """
        <div style="display: flex; justify-content: center; margin-top: 10px; margin-bottom: 40px;">
            <div title="Simplifies technical terms in your research paper to make them easier to understand.">
                <button style="padding: 10px 20px; font-size: 16px; background-color: #444; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    🔍 Jargon Simplifier
                </button>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


    # Generate button (also centered optionally)
    # Generate button centered to match Jargon Simplifier alignment
    _, col_center, _ = st.columns([1, 2, 1])  # Center column is twice as wide
    with col_center:
        if st.button("🚀 Generate"):
            st.success("Summary generated based on selected options.")
            user_question = st.text_input("💬 Ask a question about your summary:")
            if user_question:
                if "conversation" in st.session_state:
                    response = st.session_state.conversation({'question': user_question})
                    st.session_state.chat_history = response['chat_history']
                    st.write("### 📜 Chat History")
                    for msg in st.session_state.chat_history:
                        st.write(f"**{msg['role'].capitalize()}**: {msg['content']}")
                else:
                    st.warning("Conversation object not initialized.")
        else:
            st.info("Choose your settings and click 'Generate' to begin.")

if __name__ == '__main__':
    main()





#ui



