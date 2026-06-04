from __future__ import annotations

from langgraph.graph import END, StateGraph

from aiops_agent.graph.nodes import DiagnosisGraphNodes
from aiops_agent.graph.state import AIOpsDiagnosisState
from aiops_agent.services.detection_service import DetectionService
from aiops_agent.services.llm_service import GeminiLLMService
from aiops_agent.services.rag_service import RAGService


def build_diagnosis_graph(
    *,
    llm_service: GeminiLLMService | None = None,
    rag_service: RAGService | None = None,
    detection_service: DetectionService | None = None,
):
    """编译 AIOps 诊断工作流；传入 fake LLM 时不会创建真实 Gemini 客户端。"""

    nodes = DiagnosisGraphNodes(
        llm_service=llm_service,
        rag_service=rag_service,
        detection_service=detection_service,
    )
    graph = StateGraph(AIOpsDiagnosisState)
    graph.add_node("detect", nodes.detect)
    graph.add_node("build_rag_query", nodes.build_rag_query)
    graph.add_node("retrieve_k8s_docs", nodes.retrieve_k8s_docs)
    graph.add_node("gemini", nodes.gemini)
    graph.add_node("classify_commands", nodes.classify_commands)
    graph.add_node("suppress_alerts", nodes.suppress_alerts)

    graph.set_entry_point("detect")
    graph.add_edge("detect", "build_rag_query")
    graph.add_edge("build_rag_query", "retrieve_k8s_docs")
    graph.add_edge("retrieve_k8s_docs", "gemini")
    graph.add_edge("gemini", "classify_commands")
    graph.add_edge("classify_commands", "suppress_alerts")
    graph.add_edge("suppress_alerts", END)
    return graph.compile()
