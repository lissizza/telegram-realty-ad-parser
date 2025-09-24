#!/usr/bin/env python3
"""
Generate architecture diagram for the Telegram Real Estate Bot
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import RDS, ElastiCache
from diagrams.aws.storage import S3
from diagrams.generic.compute import Rack
from diagrams.generic.database import SQL
from diagrams.generic.network import Subnet
from diagrams.onprem.client import Users, Mobile
from diagrams.onprem.communication import Telegram
from diagrams.onprem.database import MongoDB, Redis
from diagrams.onprem.inmemory import Redis as RedisIcon
from diagrams.onprem.monitoring import Prometheus
from diagrams.programming.language import Python
from diagrams.saas.communication import Slack
from diagrams.aws.ai import MachineLearning

def create_architecture_diagram():
    """Create the architecture diagram"""
    
    with Diagram("Telegram Real Estate Bot Architecture", 
                 filename="docs/architecture_diagram", 
                 show=False, 
                 direction="TB"):
        
        # External services
        with Cluster("External Services"):
            telegram_channel = Telegram("Real Estate\nChannel")
            users = Users("Users")
            openai = MachineLearning("OpenAI\nGPT-3.5")
        
        # Main application
        with Cluster("Application Layer"):
            telegram_bot = Python("Telegram Bot\n(Telethon)")
            web_app = Python("Web App\n(FastAPI)")
            llm_service = Python("LLM Service")
            filter_service = Python("Filter Service")
            queue_service = Python("Queue Service")
        
        # Data layer
        with Cluster("Data Layer"):
            mongodb = MongoDB("MongoDB\n(Real Estate Ads)")
            redis_queue = Redis("Redis Queue\n(Message Processing)")
            redis_cache = RedisIcon("Redis Cache\n(Sessions)")
        
        # Processing flow
        telegram_channel >> Edge(label="New Message") >> telegram_bot
        telegram_bot >> Edge(label="Add to Queue") >> redis_queue
        redis_queue >> Edge(label="Process") >> queue_service
        queue_service >> Edge(label="Parse") >> llm_service
        llm_service >> Edge(label="Call API") >> openai
        openai >> Edge(label="Response") >> llm_service
        llm_service >> Edge(label="Save") >> mongodb
        queue_service >> Edge(label="Check Filters") >> filter_service
        filter_service >> Edge(label="Query") >> mongodb
        filter_service >> Edge(label="Forward") >> telegram_bot
        telegram_bot >> Edge(label="Send Message") >> users
        
        # Web app connections
        users >> Edge(label="Web Interface") >> web_app
        web_app >> Edge(label="API Calls") >> mongodb
        web_app >> Edge(label="Manage Filters") >> filter_service
        
        # Cache connections
        telegram_bot >> Edge(label="Cache") >> redis_cache
        web_app >> Edge(label="Cache") >> redis_cache

if __name__ == "__main__":
    create_architecture_diagram()
    print("Architecture diagram generated: docs/architecture_diagram.png")
