import React, { useState } from 'react';
import "./Menu.css"

function Menu() {
    const [isOpen, setIsOpen] = useState(false);
    const [personasName, setPersonasName] = useState("");
    const [personasDesc, setPersonasDesc] = useState("");

    const addPersona = () => {
        setIsOpen(true);
    }
    const acceptPersona = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch("https://localhost:8080/api/add_persona", {
        method: "POST",
        body: JSON.stringify({
            user_id: "example",
            persona_name: personasName,
            persona_description: personasDesc
        }),
      });

      if (response.status !== 200) {
        alert("shit happens");
        throw new Error(
          "Error while adding new persona",
        );
      }

    } catch (err) {
      console.error("Błąd: ", err);
    }
  };

    return (
        <>
      <div className="content">
          <div className="header-text">
              <h1>Choose your character!</h1>
          </div>
          <div className="personas-list">
              <form action="/ChatWindow">
                <input type="image" src="src/Menu/test_image.png" alt="Submit" width="100" height="50"/>
              </form>
              <form action={addPersona}>
                <input type="image" src="src/Menu/plus.png" alt="Submit" width="100" height="50"/>
              </form>
              {isOpen && (
                  <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50">
                      <div className="bg-white p-8 rounded shadow-lg relative">
                          <input value={personasName} type="name" className="form-control" id="persona_name_input"
                                 placeholder="Persona's name"/>
                          <textarea value={personasDesc} className="form-control" id="persona_description_textarea" rows="3"
                                    placeholder="Enter description"></textarea>
                          <button onClick={acceptPersona} className="mt-4 bg-red-500 text-white p-2 rounded">
                              Save Persona
                          </button>
                      </div>
                  </div>
              )}
          </div>
      </div>
        </>
    )
}

export default Menu;
