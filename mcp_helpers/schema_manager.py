"""
Schema management utilities for MCP integration
"""

class MCPSchemaManager:
    def __init__(self):
        self.project_name = "research-paper-summarizer"
        self.database_name = "research_db"
    
    def get_database_setup_prompt(self):
        """
        Prompt to use with MCP server for database setup
        """
        return f"""
        Please help me set up a MongoDB Atlas database for my research paper summarizer project:
        
        1. Create a database named '{self.database_name}'
        2. Set up collections: users, documents, summaries, recommendations
        3. Create appropriate indexes for performance
        4. Set up a database user with read/write permissions
        5. Configure network access for development
        
        Project context: Streamlit web application for AI-powered research paper summarization
        """
    
    def get_user_creation_prompt(self):
        """
        Prompt for creating database users
        """
        return """
        Create a database user for my research paper summarizer application:
        - Username: research_app_user
        - Password: Generate a secure password
        - Roles: readWrite on research_db database
        - Restrictions: None for development
        """
    
    def get_network_access_prompt(self):
        """
        Prompt for network access configuration
        """
        return """
        Configure network access for my research paper summarizer:
        - Add current IP address to whitelist
        - Also add 0.0.0.0/0 for development (remove in production)
        - Set up connection string for Python application
        """
