#!/usr/bin/env python3
"""
Generate simple architecture diagram for the Telegram Real Estate Bot
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.generic.compute import Rack
from diagrams.generic.database import SQL
from diagrams.generic.network import Subnet
from diagrams.onprem.client import Users
from diagrams.onprem.database import MongoDB
from diagrams.onprem.inmemory import Redis
from diagrams.programming.language import Python

def create_simple_architecture_diagram():
    """Create a simple architecture diagram"""
    
    with Diagram("Telegram Real Estate Bot - Data Flow", 
                 filename="docs/simple_architecture", 
                 show=False, 
                 direction="TB"):
        
        # External
        telegram_channel = Rack("Real Estate\nChannel")
        users = Users("Users")
        openai = Rack("OpenAI\nGPT-3.5")
        
        # Application
        with Cluster("Bot Application"):
            telegram_bot = Python("Telegram Bot")
            llm_service = Python("LLM Service")
            filter_service = Python("Filter Service")
            queue_service = Python("Queue Service")
        
        # Data
        with Cluster("Data Storage"):
            mongodb = MongoDB("MongoDB\n(Real Estate Ads)")
            redis = Redis("Redis\n(Queue & Cache)")
        
        # Flow
        telegram_channel >> Edge(label="1. New Message") >> telegram_bot
        telegram_bot >> Edge(label="2. Add to Queue") >> redis
        redis >> Edge(label="3. Process") >> queue_service
        queue_service >> Edge(label="4. Parse") >> llm_service
        llm_service >> Edge(label="5. Call API") >> openai
        openai >> Edge(label="6. Response") >> llm_service
        llm_service >> Edge(label="7. Save") >> mongodb
        queue_service >> Edge(label="8. Check Filters") >> filter_service
        filter_service >> Edge(label="9. Query") >> mongodb
        filter_service >> Edge(label="10. Forward") >> telegram_bot
        telegram_bot >> Edge(label="11. Send") >> users

if __name__ == "__main__":
    create_simple_architecture_diagram()
    print("Simple architecture diagram generated: docs/simple_architecture.png")
