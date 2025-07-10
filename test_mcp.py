"""
Test MCP integration with your research paper summarizer
"""

def test_mcp_connection():
    """
    Test prompts to verify MCP server is working
    """
    test_prompts = [
        "List all MongoDB Atlas projects accessible to me",
        "Show me the clusters in my research paper summarizer project",
        "Help me create a database user with read/write permissions",
        "Generate a MongoDB query to find all users created in the last 7 days",
        "Suggest optimal indexes for a documents collection with user_id and upload_date fields"
    ]
    
    print("=== MCP Connection Test Prompts ===")
    print("Use these prompts with your AI assistant to test MCP integration:\n")
    
    for i, prompt in enumerate(test_prompts, 1):
        print(f"{i}. {prompt}")
    
    print("\nIf your AI assistant can respond to these prompts with MongoDB-specific information,")
    print("your MCP server is configured correctly!")

if __name__ == "__main__":
    test_mcp_connection()
