# tests/test_persona_images.py
import sys
import pytest
import os
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from io import BytesIO

sys.path.append(
    os.path.dirname( # AIPersonas
        os.path.dirname( # AIPersonas\tests
            os.path.dirname( # AIPersonas\tests\backend
                os.path.dirname( # AIPersonas\tests\backend\backend_tests
                    os.path.abspath(  # AIPersonas\tests\backend\test_integration.py
                        __file__ 
                    )
                )
            )
        )
    )
)

from main  import app

class TestIntegration:

    def test_integration_debug_routes(self, client):
        for route in app.routes:
            print(f"Route: {route.path} - Methods: {getattr(route, 'methods', 'N/A')}")

    def test_integration_e2e_conversation(self, client, override_auth):
        """Test a complete workflow: create persona -> chat -> export PDF"""
        # Step 1: Create new persona
        persona_data = {
            "persona_name": "WorkflowBot",
            "persona_description": "A bot for testing workflows"
        }
        
        mock_persona_id = 999
        mock_conversation_id = 888
        
        with patch("backend.main.insert_persona_and_conversation", new_callable=AsyncMock) as mock_insert, \
                patch("backend.main.embed_character") as mock_embed, \
                patch("builtins.open", create=True):
            
            mock_insert.return_value = (mock_persona_id, mock_conversation_id)
            
            # Create persona
            response = client.post("/api/new_persona", json=persona_data)
            assert response.status_code == 200
            
            # Step 2: Send message and get answer
            message_data = {
                "prompt": "Hello WorkflowBot!",
                "persona": "WorkflowBot",
                "conversation_id": mock_conversation_id,
                "temperature": 0.7
            }
            
            with patch("backend.main.save_message", new_callable=AsyncMock), \
                    patch("backend.main.ask_character") as mock_ask, \
                    patch("backend.main.SenderType") as mock_sender_type:
                
                mock_ask.return_value = "Hello! I'm WorkflowBot, ready to help!"
                mock_sender_type.USER = "USER"
                mock_sender_type.BOT = "BOT"
                
                response = client.post("/api/get_answer", json=message_data)
                assert response.status_code == 200
                
                # Step 3: Export conversation to PDF
                conversation_data = {"conversation_id": mock_conversation_id}
                
                mock_persona = Mock()
                mock_persona.name = "WorkflowBot"
                mock_messages = [{"content": "Hello!", "sender": "user"}]
                mock_pdf_stream = BytesIO(b"workflow pdf content")
                
                with patch("backend.main.get_persona_by_conversation_id", new_callable=AsyncMock) as mock_get_persona, \
                        patch("backend.main.get_messages_from_conversation", new_callable=AsyncMock) as mock_get_messages, \
                        patch("backend.main.get_pdf_conversation") as mock_get_pdf, \
                        patch("backend.main.datetime") as mock_datetime:
                    
                    mock_get_persona.return_value = mock_persona
                    mock_get_messages.return_value = mock_messages
                    mock_get_pdf.return_value = mock_pdf_stream
                    mock_datetime.now.return_value = "2024-01-01"
                    
                    response = client.post("/api/pdf_conversation", json=conversation_data)
                    assert response.status_code == 200
                    assert response.headers["content-type"] == "application/pdf"

    def test_integration_e2e_create_persona(self, client, override_auth):
        """Integration test: Login -> Get User Personas -> Create new persona -> Get user personas again"""
        
        # Initial state - user has existing personas
        initial_personas = [
            {"id": 1, "name": "Assistant", "description": "Helpful AI"},
            {"id": 2, "name": "Teacher", "description": "Educational AI"}
        ]
        
        # After creating new persona
        updated_personas = [
            {"id": 1, "name": "Assistant", "description": "Helpful AI"},
            {"id": 2, "name": "Teacher", "description": "Educational AI"},
            {"id": 3, "name": "NewBot", "description": "A newly created bot"}
        ]
        
        new_persona_data = {
            "persona_name": "NewBot",
            "persona_description": "A newly created bot"
        }
        
        mock_persona_id = 3
        mock_conversation_id = 333
        
        with patch("backend.main.get_all_user_personas", new_callable=AsyncMock) as mock_get_personas, \
            patch("backend.main.insert_persona_and_conversation", new_callable=AsyncMock) as mock_insert, \
            patch("backend.main.embed_character") as mock_embed, \
            patch("builtins.open", create=True) as mock_open:
            
            mock_insert.return_value = (mock_persona_id, mock_conversation_id)
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            mock_get_personas.side_effect = [initial_personas, updated_personas]
            
            # Step 1: Get initial user personas
            response = client.post("/api/get_user_personas")
            assert response.status_code == 200
            initial_data = response.json()
            assert len(initial_data["persona_names"]) == 2
            assert initial_data["persona_names"] == initial_personas
            
            # Step 2: Create new persona
            response = client.post("/api/new_persona", json=new_persona_data)
            assert response.status_code == 200
            create_data = response.json()
            assert create_data["persona_id"] == mock_persona_id
            assert create_data["persona_name"] == new_persona_data["persona_name"]
            assert create_data["conversation_id"] == mock_conversation_id
            
            # Step 3: Get user personas again to verify addition
            response = client.post("/api/get_user_personas")
            assert response.status_code == 200
            final_data = response.json()
            assert len(final_data["persona_names"]) == 3
            assert final_data["persona_names"] == updated_personas
            
            # Verify the new persona is in the list
            new_persona = next(p for p in final_data["persona_names"] if p["name"] == "NewBot")
            assert new_persona["description"] == "A newly created bot"
            
            # Verify all mocks were called correctly
            assert mock_get_personas.call_count == 2
            mock_insert.assert_called_once_with(
                override_auth.id, 
                new_persona_data["persona_name"], 
                new_persona_data["persona_description"]
            )
            mock_embed.assert_called_once()
            mock_file.write.assert_called_once()


    def test_integration_e2e_update_persona(self, client, override_auth):
        """Integration test: Login -> Get User Personas -> Update persona description -> Get User Personas again"""
        
        # Initial state - user has existing personas
        initial_personas = [
            {"id": 1, "name": "Assistant", "description": "Helpful AI"},
            {"id": 2, "name": "Teacher", "description": "Educational AI"}
        ]
        
        # After updating persona description
        updated_personas = [
            {"id": 1, "name": "Assistant", "description": "Helpful AI"},
            {"id": 2, "name": "Teacher", "description": "Advanced Educational AI with deep knowledge"}
        ]
        
        update_data = {
            "persona_id": 2,
            "new_description": "Advanced Educational AI with deep knowledge"
        }
        
        # Mock persona object for the update
        mock_persona = Mock()
        mock_persona.user_id = override_auth.id
        mock_persona.name = "Teacher"
        mock_persona.description = "Educational AI"  # Original description
        
        with patch("backend.main.get_all_user_personas", new_callable=AsyncMock) as mock_get_personas, \
            patch("backend.main.get_persona_by_id", new_callable=AsyncMock) as mock_get_persona, \
            patch("backend.main.db_update_persona_description", new_callable=AsyncMock) as mock_update_db, \
            patch("backend.main.embed_character") as mock_embed, \
            patch("builtins.open", create=True) as mock_open:
            
            mock_get_persona.return_value = mock_persona
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            mock_get_personas.side_effect = [initial_personas, updated_personas]
            
            # Step 1: Get initial user personas
            response = client.post("/api/get_user_personas")
            assert response.status_code == 200
            initial_data = response.json()
            assert len(initial_data["persona_names"]) == 2
            
            # Find the persona we're going to update
            teacher_persona = next(p for p in initial_data["persona_names"] if p["name"] == "Teacher")
            assert teacher_persona["description"] == "Educational AI"
            
            # Step 2: Update persona description
            response = client.post("/api/update_persona_description", json=update_data)
            assert response.status_code == 200
            update_response = response.json()
            assert update_response["message"] == "Persona description updated successfully"
            
            # Step 3: Get user personas again to verify the update
            response = client.post("/api/get_user_personas")
            assert response.status_code == 200
            final_data = response.json()
            assert len(final_data["persona_names"]) == 2  # Same number of personas
            
            # Verify the description was updated
            updated_teacher = next(p for p in final_data["persona_names"] if p["name"] == "Teacher")
            assert updated_teacher["description"] == "Advanced Educational AI with deep knowledge"
            
            # Verify the other persona remained unchanged
            assistant_persona = next(p for p in final_data["persona_names"] if p["name"] == "Assistant")
            assert assistant_persona["description"] == "Helpful AI"
            
            assert mock_get_personas.call_count == 2
            mock_get_persona.assert_called_once_with(update_data["persona_id"])
            mock_update_db.assert_called_once_with(
                update_data["persona_id"], 
                update_data["new_description"]
            )
            mock_embed.assert_called_once()
            mock_file.write.assert_called_once_with(
                f"# {mock_persona.name}\n\n{update_data['new_description']}\n"
            )