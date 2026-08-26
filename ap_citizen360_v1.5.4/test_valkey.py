import asyncio
from langchain_core.messages import HumanMessage
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from my_agent.agent import build_graph
from my_agent.utils.tools import cleanup_tools

async def main():
    graph = await build_graph()
    user_query = "List dropout students from AAY ration-card households in Anantapur in 2025-26."
    
    print("=== First Run (should Miss) ===")
    res1 = await graph.ainvoke({"user_query": user_query, "messages": [HumanMessage(content=user_query)], "llm_calls": 0, "rag_calls": 0, "verify_calls": 0})
    
    print("\n=== Second Run (should Miss) ===")
    res2 = await graph.ainvoke({"user_query": user_query, "messages": [HumanMessage(content=user_query)], "llm_calls": 0, "rag_calls": 0, "verify_calls": 0})
    
    print("\n=== Third Run (should hit Threshold and Save) ===")
    res3 = await graph.ainvoke({"user_query": user_query, "messages": [HumanMessage(content=user_query)], "llm_calls": 0, "rag_calls": 0, "verify_calls": 0})
    
    print("\n=== Fourth Run (should hit Exact Cache and return fast_sql) ===")
    res4 = await graph.ainvoke({"user_query": user_query, "messages": [HumanMessage(content=user_query)], "llm_calls": 0, "rag_calls": 0, "verify_calls": 0})
    print(f"Fast SQL: {res4.get('fast_sql')}")
    
    # Test semantic match with slight variation
    print("\n=== Fifth Run (Semantic Check) ===")
    var_query = "Show me dropout students from AAY ration-card households in Anantapur for 2025-26."
    res5 = await graph.ainvoke({"user_query": var_query, "messages": [HumanMessage(content=var_query)], "llm_calls": 0, "rag_calls": 0, "verify_calls": 0})
    print(f"Fast SQL (Semantic): {res5.get('fast_sql')}")

    await cleanup_tools()

if __name__ == "__main__":
    asyncio.run(main())
