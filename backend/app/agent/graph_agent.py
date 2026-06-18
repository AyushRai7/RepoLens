from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import TypedDict, Annotated
import operator
import logging

from app.config import get_settings
from app.agent.prompts import SYSTEM_PROMPT, NODE_SCOPED_PROMPT

logger = logging.getLogger(__name__)
settings = get_settings()

_MODEL = "llama-3.3-70b-versatile"


class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    repo_full_name: str
    scoped_file: str | None


def build_agent(db, repo_id: str, repo_full_name: str, retriever, scoped_file: str | None = None):
    if scoped_file:
        from app.db.models import CodeFile
        file = db.query(CodeFile).filter_by(repo_id=repo_id, path=scoped_file).first()
        base_system = NODE_SCOPED_PROMPT.format(
            file_path=scoped_file,
            file_summary=file.ai_summary if file else "unknown",
            language=file.language if file else "unknown",
            functions=(
                ", ".join(f["name"] for f in (file.functions or [])[:10])
                if file else "none"
            ),
        )
    else:
        base_system = SYSTEM_PROMPT.format(repo_full_name=repo_full_name)

    llm = ChatGroq(
        model=_MODEL,
        api_key=settings.groq_api_key,
        temperature=0.2,
        max_tokens=2048,
    )

    def call_model(state: AgentState):
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )

        rag_context = ""
        if last_human and retriever:
            try:
                query = last_human.content
                if "[User question]" in query:
                    query = query.split("[User question]")[-1].strip()
                docs = retriever.invoke(query[:600])
                if docs:
                    snippets = []
                    for doc in docs[:6]:
                        path = doc.metadata.get("path", "unknown")
                        lang = doc.metadata.get("language", "")
                        snippets.append(f"### {path} ({lang})\n```\n{doc.page_content[:800]}\n```")
                    rag_context = "\n\nRelevant code from the repository:\n\n" + "\n\n".join(snippets)
            except Exception as e:
                logger.warning("RAG retrieval failed: %s", e)

        messages = [SystemMessage(content=base_system + rag_context)] + state["messages"]
        try:
            response = llm.invoke(messages)
            return {"messages": [response]}
        except Exception as e:
            logger.error("LLM call failed for %s: %s", repo_full_name, e, exc_info=True)
            return {"messages": [AIMessage(content="I encountered an error. Please try rephrasing your question.")]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.set_entry_point("agent")
    graph.add_edge("agent", END)
    return graph.compile()