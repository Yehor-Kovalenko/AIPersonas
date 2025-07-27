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
                os.path.abspath(  # AIPersonas\tests\backend\test_endpoints.py
                    __file__ 
                )
            )
        )
    )
)

from main  import app

# client = TestClient(app)

class TestAllEndpoints:

    # Add this test to see all registered routes
    def test_debug_routes(self, client):
        for route in app.routes:
            print(f"Route: {route.path} - Methods: {getattr(route, 'methods', 'N/A')}")

    def test_get_existing_persona_image(self, client):
        """Test getting a default persona image"""
        # Check what files exist in your personas directory
        personas_dir = Path("backend/personas")
        if personas_dir.exists():
            existing_files = list(personas_dir.glob("*.png"))
            if existing_files:
                # Test with the first existing file
                filename = existing_files[0].name
                response = client.get(f"/static/personas/{filename}")
                
                assert response.status_code == 200
                assert len(response.content) > 0
                # Check cache headers
                assert response.headers["cache-control"] == "no-cache, no-store, must-revalidate"
            else:
                pytest.skip("No default persona images found")
        else:
            pytest.skip("Personas directory doesn't exist")

    def test_get_persona_image_not_found(self, client):
        """Test 404 when file doesn't exist"""
        response = client.get(url="/static/personas/nonexistent_image.png")
        
        assert response.status_code == 404
        assert response.json() == {"detail": "Image not found"}

    @pytest.mark.parametrize("filename", [
        "../../../etc/passwd",
        "subdir/image.png", 
        "image..png"
    ])
    def test_get_persona_image_invalid_paths(self, client, filename):
        """Test security - invalid file paths"""
        response = client.get(f"/static/personas/{filename}")
        
        # Should return 404 (file doesn't exist in personas dir)
        assert response.status_code == 404


    def test_get_user_personas_success(self, client, override_auth):
            """Test successful retrieval of user personas"""
            mock_personas = [
                {"id": 1, "name": "Assistant", "description": "Helpful AI"},
                {"id": 2, "name": "Teacher", "description": "Educational AI"}
            ]
            
            with patch("backend.main.get_all_user_personas", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_personas
                
                response = client.post("/api/get_user_personas")
                
                assert response.status_code == 200
                data = response.json()
                assert "persona_names" in data
                assert data["persona_names"] == mock_personas
                mock_get.assert_called_once_with(override_auth.id)

    def test_add_persona_success(self, client, override_auth):
        """Test successful persona addition"""
        persona_data = {
            "persona_name": "New Assistant",
            "persona_description": "A helpful AI assistant"
        }
        
        mock_persona_id = 123
        mock_conversation_id = 456
        
        with patch("backend.main.insert_persona_and_conversation", new_callable=AsyncMock) as mock_insert:
            mock_insert.return_value = (mock_persona_id, mock_conversation_id)
            
            response = client.post("/api/add_persona", json=persona_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["persona_id"] == mock_persona_id
            assert data["persona_name"] == persona_data["persona_name"]
            assert data["user_id"] == override_auth.id
            assert data["conversation_id"] == mock_conversation_id
            mock_insert.assert_called_once_with(
                override_auth.id, 
                persona_data["persona_name"], 
                persona_data["persona_description"]
            )

    def test_add_new_persona_success(self, client, override_auth):
        """Test successful new persona creation with embedding"""
        persona_data = {
            "persona_name": "TestBot",
            "persona_description": "A test chatbot"
        }
        
        mock_persona_id = 789
        mock_conversation_id = 101
        
        with patch("backend.main.insert_persona_and_conversation", new_callable=AsyncMock) as mock_insert, \
                patch("backend.main.embed_character") as mock_embed, \
                patch("builtins.open", create=True) as mock_open:
            
            mock_insert.return_value = (mock_persona_id, mock_conversation_id)
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            response = client.post("/api/new_persona", json=persona_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["persona_id"] == mock_persona_id
            assert data["persona_name"] == persona_data["persona_name"]
            assert data["user_id"] == override_auth.id
            assert data["conversation_id"] == mock_conversation_id
            
            # Verify file writing
            mock_open.assert_called_once()
            mock_file.write.assert_called_once_with(
                f"# {persona_data['persona_name']}\n\n{persona_data['persona_description']}\n"
            )
            
            # Verify embedding call
            mock_embed.assert_called_once_with(
                character_name=persona_data["persona_name"],
                encoder_path="google-bert/bert-large-uncased",
                seed_data_path="../Neeko/data/seed_data",
                save_path="../Neeko/data/embed"
            )

    def test_get_chats_history_success(self, client, override_auth):
        """Test successful retrieval of chat history"""
        conversation_data = {"conversation_id": 123}
        mock_messages = [
            {"id": 1, "content": "Hello", "sender": "user"},
            {"id": 2, "content": "Hi there!", "sender": "bot"}
        ]
        
        with patch("backend.main.get_messages_from_conversation", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_messages
            
            response = client.post("/api/chat_history", json=conversation_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "messages" in data
            assert data["messages"] == mock_messages
            mock_get.assert_called_once_with(conversation_data["conversation_id"])

    def test_send_user_message_success(self, client, override_auth):
        """Test successful user message sending"""
        message_data = {
            "prompt": "Hello, how are you?",
            "persona": "Assistant",
            "conversation_id": 123,
            "temperature": 0.7
        }
        
        response = client.post("/api/user_message", json=message_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["prompt"] == message_data["prompt"]
        assert data["response"] == "I got your message"
        assert data["user_id"] == override_auth.id
        assert data["user_email"] == override_auth.email

    def test_get_answer_success(self, client, override_auth):
        """Test successful answer generation"""
        message_data = {
            "prompt": "What is AI?",
            "persona": "Teacher",
            "conversation_id": 456,
            "temperature": 0.5
        }
        
        mock_generated_text = "AI is artificial intelligence, a field of computer science..."
        
        with patch("backend.main.save_message", new_callable=AsyncMock) as mock_save, \
                patch("backend.main.ask_character") as mock_ask, \
                patch("backend.main.SenderType") as mock_sender_type:
            
            mock_ask.return_value = mock_generated_text
            mock_sender_type.USER = "USER"
            mock_sender_type.BOT = "BOT"
            
            response = client.post("/api/get_answer", json=message_data)
            
            assert response.status_code == 200
            assert response.json() == mock_generated_text
            
            # Verify message saving
            assert mock_save.call_count == 2
            # First call - save user message
            mock_save.assert_any_call(
                message_data["conversation_id"], 
                mock_sender_type.USER, 
                message_data["prompt"]
            )
            # Second call - save bot response
            mock_save.assert_any_call(
                message_data["conversation_id"], 
                mock_sender_type.BOT, 
                mock_generated_text
            )
            
            # Verify AI generation call
            mock_ask.assert_called_once()

    def test_pdf_conversation_success(self, client, override_auth):
        """Test successful PDF conversation export"""
        conversation_data = {"conversation_id": 789}
        
        mock_persona = Mock()
        mock_persona.name = "TestBot"
        
        mock_messages = [
            {"content": "Hello", "sender": "user"},
            {"content": "Hi!", "sender": "bot"}
        ]
        
        mock_pdf_stream = BytesIO(b"fake pdf content")
        
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
            assert "attachment" in response.headers["content-disposition"]
            assert "conversation_with_TestBot.pdf" in response.headers["content-disposition"]
            
            # Verify calls
            mock_get_persona.assert_called_once_with(conversation_data["conversation_id"])
            mock_get_messages.assert_called_once_with(conversation_data["conversation_id"])
            mock_get_pdf.assert_called_once()

    def test_get_persona_description_success(self, client, override_auth):
        """Test successful persona description retrieval"""
        persona_id = 123
        mock_persona = Mock()
        mock_persona.user_id = override_auth.id
        mock_persona.description = "A helpful AI assistant"
        
        with patch("backend.main.get_persona_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_persona
            
            response = client.get(f"/api/get_persona_description/{persona_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["description"] == mock_persona.description
            mock_get.assert_called_once_with(persona_id)

    def test_update_persona_description_success(self, client, override_auth):
        """Test successful persona description update"""
        update_data = {
            "persona_id": 456,
            "new_description": "Updated AI assistant description"
        }
        
        mock_persona = Mock()
        mock_persona.user_id = override_auth.id
        mock_persona.name = "TestBot"
        
        with patch("backend.main.get_persona_by_id", new_callable=AsyncMock) as mock_get, \
                patch("backend.main.db_update_persona_description", new_callable=AsyncMock) as mock_update, \
                patch("backend.main.embed_character") as mock_embed, \
                patch("builtins.open", create=True) as mock_open:
            
            mock_get.return_value = mock_persona
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            response = client.post("/api/update_persona_description", json=update_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Persona description updated successfully"
            
            # Verify database update
            mock_update.assert_called_once_with(
                update_data["persona_id"], 
                update_data["new_description"]
            )
            
            # Verify file update
            mock_open.assert_called_once()
            mock_file.write.assert_called_once_with(
                f"# {mock_persona.name}\n\n{update_data['new_description']}\n"
            )
            
            # Verify re-embedding
            mock_embed.assert_called_once()

    def test_transcribe_audio_success(self, client):
        """Test successful audio transcription"""
        # Create a fake audio file
        fake_audio_content = b"fake audio content"
        
        mock_transcription_result = {
            "text": "Hello, this is a test transcription"
        }
        
        with patch("backend.main.backend.voice_communication.transcribe_audio_file") as mock_transcribe, \
                patch("tempfile.NamedTemporaryFile") as mock_temp, \
                patch("os.path.exists") as mock_exists, \
                patch("os.remove") as mock_remove:
            
            # Setup mocks
            mock_transcribe.return_value = mock_transcription_result
            mock_temp_file = Mock()
            mock_temp_file.name = "/tmp/test_audio.mp3"
            mock_temp.return_value.__enter__.return_value = mock_temp_file
            mock_exists.return_value = True
            
            # Create file upload
            files = {"file": ("test_audio.mp3", BytesIO(fake_audio_content), "audio/mpeg")}
            
            response = client.post("/transcribe", files=files)
            
            assert response.status_code == 200
            data = response.json()
            assert data["text"] == mock_transcription_result["text"]
            
            # Verify transcription was called
            mock_transcribe.assert_called_once()
            
            # Verify cleanup
            mock_remove.assert_called_once_with(mock_temp_file.name)

    def test_transcribe_audio_m4a_success(self, client):
        """Test successful audio transcription with m4a file"""
        fake_audio_content = b"fake m4a audio content"
        
        mock_transcription_result = {
            "text": "This is an m4a transcription test"
        }
        
        with patch("backend.main.backend.voice_communication.transcribe_audio_file") as mock_transcribe, \
                patch("tempfile.NamedTemporaryFile") as mock_temp, \
                patch("os.path.exists") as mock_exists, \
                patch("os.remove") as mock_remove:
            
            mock_transcribe.return_value = mock_transcription_result
            mock_temp_file = Mock()
            mock_temp_file.name = "/tmp/test_audio.m4a"
            mock_temp.return_value.__enter__.return_value = mock_temp_file
            mock_exists.return_value = True
            
            files = {"file": ("test_audio.m4a", BytesIO(fake_audio_content), "audio/mp4")}
            
            response = client.post("/transcribe", files=files)
            
            assert response.status_code == 200
            data = response.json()
            assert data["text"] == mock_transcription_result["text"]
            
            mock_transcribe.assert_called_once()
            mock_remove.assert_called_once_with(mock_temp_file.name)

    def test_allowed_file_function_success(self):
        """Test the allowed_file helper function"""
        from main import allowed_file
        
        # Test valid extensions
        assert allowed_file("test.mp3") == True
        assert allowed_file("test.m4a") == True
        assert allowed_file("audio_file.MP3") == True  # Case insensitive
        assert allowed_file("voice_note.M4A") == True
        
        # Test invalid extensions
        assert allowed_file("test.wav") == False
        assert allowed_file("test.txt") == False
        assert allowed_file("noextension") == False
        assert allowed_file("test.") == False

    def test_comprehensive_workflow(self, client, override_auth):
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

    def test_integration_create_persona_workflow(self, client, override_auth):
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
            
            # Setup mock returns
            mock_insert.return_value = (mock_persona_id, mock_conversation_id)
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            # Configure get_all_user_personas to return different results for each call
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


    def test_integration_update_persona_description_workflow(self, client, override_auth):
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
            
            # Setup mock returns
            mock_get_persona.return_value = mock_persona
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            # Configure get_all_user_personas to return different results for each call
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
            
            # Verify all mocks were called correctly
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