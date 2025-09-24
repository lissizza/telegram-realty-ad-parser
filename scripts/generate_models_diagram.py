#!/usr/bin/env python3
"""
Generate data models diagram for the Telegram Real Estate Bot
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.generic.compute import Rack
from diagrams.generic.database import SQL
from diagrams.onprem.database import MongoDB
from diagrams.programming.language import Python

def create_models_diagram():
    """Create data models diagram"""
    
    with Diagram("Data Models Architecture", 
                 filename="docs/models_diagram", 
                 show=False, 
                 direction="TB"):
        
        # External sources
        telegram_channel = Rack("Telegram\nChannel")
        users = Rack("Users")
        
        # Models
        with Cluster("Data Models"):
            incoming_msg = Python("IncomingMessage\n(Received from channels)")
            queued_msg = Python("QueuedMessage\n(Processing queue)")
            real_estate_ad = Python("RealEstateAd\n(Parsed real estate)")
            outgoing_post = Python("OutgoingPost\n(Sent to users)")
            simple_filter = Python("SimpleFilter\n(User filters)")
        
        # Database
        mongodb = MongoDB("MongoDB\nDatabase")
        
        # Flow
        telegram_channel >> Edge(label="1. New Message") >> incoming_msg
        incoming_msg >> Edge(label="2. Add to Queue") >> queued_msg
        queued_msg >> Edge(label="3. LLM Parse") >> real_estate_ad
        real_estate_ad >> Edge(label="4. Check Filters") >> simple_filter
        simple_filter >> Edge(label="5. Match") >> outgoing_post
        outgoing_post >> Edge(label="6. Send") >> users
        
        # Database connections
        real_estate_ad >> Edge(label="Save") >> mongodb
        simple_filter >> Edge(label="Query") >> mongodb
        outgoing_post >> Edge(label="Log") >> mongodb

if __name__ == "__main__":
    create_models_diagram()
    print("Models diagram generated: docs/models_diagram.png")
