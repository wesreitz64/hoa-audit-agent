from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
import os

load_dotenv()

def create_agent():
    # Connect to the SQLite DB we just created
    db = SQLDatabase.from_uri("sqlite:///data/audit.db")

    # Use Claude 3.5 Sonnet or gpt-4o for the SQL translations
    # Claude is typically better at SQL generation
    llm = ChatAnthropic(temperature=0, model="claude-3-5-sonnet-20241022")
    
    agent_executor = create_sql_agent(
        llm=llm,
        db=db,
        agent_type="openai-tools", # Langchain uses this term for tool-calling agents
        verbose=False,
        max_iterations=5
    )
    
    return agent_executor

def run_chat():
    print("\n===============================")
    print("HOA AUDIT SWARM: SQL AGENT ONLINE")
    print("Type 'exit' to quit.")
    print("===============================\n")
    
    agent = create_agent()
    
    while True:
        try:
            query = input("Ask the Auditor: ")
            if query.lower() in ['exit', 'quit']:
                break
                
            print("\nThinking...")
            response = agent.invoke({"input": query})
            print(f"\n🤖: {response['output']}\n")
            
        except sqlite3.OperationalError as e:
            print(f"SQL Error: {e}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run_chat()
