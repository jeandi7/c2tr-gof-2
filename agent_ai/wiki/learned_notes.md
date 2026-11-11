# Learned Notes — GoF Wiki Agent

### Memento
* **Problem Context**: Saving and restoring editor document states to support undo operations without exposing internal details.
* **Key Components**:
	+ **Editor**: Manages document state and interactions with the caretaker.
	+ **Memento**: A snapshot of the document state, saved and restored by the caretaker.
	+ **Caretaker**: Manages the creation and restoration of mementos, interacting with the editor.
* **Domain Example**: A text editor with undo functionality, where the caretaker saves and restores memento snapshots of the document state.
* **Pitfall**: Over-exposing internal details by having the editor or document directly interact with the undo logic.
* **Naming Choice**: Use a caretaker to manage memento snapshots, rather than exposing the editor or document's internal state directly.
* **Key Takeaway**: The caretaker's save and restore methods should be used to manage memento snapshots, while the editor's save method should be used to create a new memento instance.
* **Additional Consideration**: Utilize the Command pattern to encapsulate undo operations, with the Invoker managing the execution and undo logic.
