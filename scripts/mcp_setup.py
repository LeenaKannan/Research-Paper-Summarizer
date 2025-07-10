#!/usr/bin/env python3
"""
MCP-assisted setup script for research paper summarizer
Run this after configuring MCP server
"""

from mcp_helpers.database_setup import get_collection_schemas, get_required_indexes
from mcp_helpers.schema_manager import MCPSchemaManager
import json

def main():
    print("=== MCP Setup Assistant ===")
    print("Use these prompts with your MCP-enabled AI assistant:\n")
    
    schema_manager = MCPSchemaManager()
    
    print("1. DATABASE SETUP PROMPT:")
    print("-" * 50)
    print(schema_manager.get_database_setup_prompt())
    print("\n")
    
    print("2. USER CREATION PROMPT:")
    print("-" * 50)
    print(schema_manager.get_user_creation_prompt())
    print("\n")
    
    print("3. NETWORK ACCESS PROMPT:")
    print("-" * 50)
    print(schema_manager.get_network_access_prompt())
    print("\n")
    
    print("4. COLLECTION SCHEMAS:")
    print("-" * 50)
    schemas = get_collection_schemas()
    print(json.dumps(schemas, indent=2))
    print("\n")
    
    print("5. REQUIRED INDEXES:")
    print("-" * 50)
    indexes = get_required_indexes()
    print(json.dumps(indexes, indent=2))
    print("\n")
    
    print("Copy these prompts and use them with your MCP-enabled AI assistant!")

if __name__ == "__main__":
    main()
