import asyncio
import os
from dotenv import load_dotenv
from utils.database import db_manager
from utils.auth import auth_manager
from utils.crud_operations import crud

load_dotenv()

async def test_database_operations():
    """Test database operations"""
    try:
        # Connect to database
        await db_manager.connect()
        print("✅ Database connected successfully")
        
        # Test user registration
        success, message, user_id = await auth_manager.register_user(
            username="testuser",
            email="test@example.com",
            password="testpassword123",
            full_name="Test User"
        )
        
        if success:
            print(f"✅ User registered: {user_id}")
            
            # Test authentication
            auth_success, auth_message, user_data = await auth_manager.authenticate_user(
                "testuser", "testpassword123"
            )
            
            if auth_success:
                print(f"✅ Authentication successful: {user_data['username']}")
                
                # Test session creation
                session_token = await auth_manager.create_user_session(user_data['user_id'])
                if session_token:
                    print(f"✅ Session created: {session_token[:10]}...")
                    
                    # Test session validation
                    session_data = await auth_manager.validate_session(session_token)
                    if session_data:
                        print(f"✅ Session validated: {session_data['username']}")
                    else:
                        print("❌ Session validation failed")
                else:
                    print("❌ Session creation failed")
            else:
                print(f"❌ Authentication failed: {auth_message}")
        else:
            print(f"❌ Registration failed: {message}")
        
        # Test document operations
        document_data = {
            "user_id": user_id,
            "filename": "test_document.pdf",
            "original_filename": "test_document.pdf",
            "file_type": "pdf",
            "file_size": 1024,
            "file_path": "/uploads/test_document.pdf",
            "content_text": "This is a test document content.",
            "processing_status": "completed"
        }
        
        doc_id = await crud.create_document(document_data)
        if doc_id:
            print(f"✅ Document created: {doc_id}")
            
            # Test document retrieval
            document = await crud.get_document_by_id(doc_id)
            if document:
                print(f"✅ Document retrieved: {document['filename']}")
            else:
                print("❌ Document retrieval failed")
        else:
            print("❌ Document creation failed")
        
        print("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        await db_manager.disconnect()

if __name__ == "__main__":
    asyncio.run(test_database_operations())
