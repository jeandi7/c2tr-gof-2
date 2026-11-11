# GoF Pattern Usage Rules

Extracted from *Design Patterns UML* — A. Beugnard, ENST Bretagne, 1999.

The **Structural signature** of each pattern is the canonical schema used by `compute_comprehension()` to score Φᵢ ∈ [0, 10]. It is defined in [gof/schema.py](gof/schema.py).

---

## Creational Patterns

### AbstractFactory
Use AbstractFactory when:
- A system must be independent of how its products are created, assembled, and represented.
- A system relies on a product from a family of products.
- A family of products must be used together, and this constraint must be enforced.
- You want to define a single interface for a family of concrete products.

**Structural signature**

| | |
|-|-|
| Min classes | 4 — AbstractFactory, ConcreteFactory, AbstractProduct, ConcreteProduct |
| Relationship types | `inheritance`, `dependency` |
| Key methods | `createproduct`, `create` |

---

### Builder
Use Builder when:
- The algorithm for creating an object must be independent of the parts it is composed of and how they are assembled.
- The construction process must allow different representations of the constructed object.

**Structural signature**

| | |
|-|-|
| Min classes | 3 — Builder, ConcreteBuilder, Director |
| Relationship types | `association`, `dependency` |
| Key methods | `build`, `getresult`, `construct` |

---

### FactoryMethod
Use FactoryMethod when:
- A class cannot anticipate which class of object it must create.
- A class delegates creation responsibility to its subclasses while centralising the interface in a single class.

**Structural signature**

| | |
|-|-|
| Min classes | 3 — Creator, ConcreteCreator, Product |
| Relationship types | `inheritance`, `dependency` |
| Key methods | `factorymethod`, `create` |

---

### Prototype
Use Prototype when:
- A system must be independent of how its products are created, assembled, and represented.
- The class is only known at runtime.
- You want to avoid a parallel Factory hierarchy mirroring a product hierarchy.

**Structural signature**

| | |
|-|-|
| Min classes | 2 — Prototype, ConcretePrototype |
| Relationship types | `inheritance` |
| Key methods | `clone` |

---

### Singleton
Use Singleton when:
- There is exactly one instance of a class and it must be accessible in a well-known way.
- The unique instance can be subclassed and clients can reference that extension without modifying their code.

**Mandatory method — always include:**
- The Singleton class MUST expose `+ getInstance(): ClassName` as a public static method.
  This is the canonical access point and the only way for clients to obtain the unique instance.
  Example: `+ getInstance(): DiskManager`, `+ getInstance(): Logger`.

**Domain rule — identifying the Singleton class:**
- Read the objective and find the entity described as unique, singular, or globally shared
  (keywords: "single", "unique", "only one", "global", "shared").
- Name the class after the domain concept, not after the pattern role
  (prefer `DiskManager`, `Logger`, `Registry` over `Singleton`).
- If the objective describes a single resource that manages or contains others
  (e.g., "a single disk containing all partitions"), that resource is the Singleton class.

**Structural signature**

| | |
|-|-|
| Min classes | 1 — Singleton |
| Relationship types | *(none)* |
| Key methods | `getInstance` |

---

## Structural Patterns

### Adapter
Use Adapter when you want to use:
- An existing class whose interface does not match the required one.
- Several subclasses where redefining each interface by subclassing is too costly; an Adapter can adapt the interface at the parent level.

**Structural signature**

| | |
|-|-|
| Min classes | 3 — Target, Adapter, Adaptee |
| Relationship types | `inheritance`, `association` |
| Key methods | `request`, `specificrequest` |

---

### Bridge
Use Bridge when:
- You want to avoid a permanent binding between abstraction and implementation (e.g., the implementation is chosen at runtime).
- Both abstraction and implementation should be independently refineable.
- Changes to the implementation or abstraction must not impact the client (no recompilation).

**Domain rule — identifying Bridge candidates:**
- A Bridge connects **two different domains**: a **business/domain** layer (the concept the client
  reasons about) and a **technical/infrastructure** layer (an OS, a hardware format, a protocol, a
  storage engine) that can have several interchangeable variants.
- Keywords: "must support multiple formats/protocols/backends", "interacts with the operating
  system / disk / hardware", "several implementations of the same technical service",
  "independently of the underlying technology".
- The **Abstraction** is the business-facing class (e.g. `LogicalUnit`, `FileSystem`) — what the rest
  of the domain model talks to.
- The **Implementor** hierarchy is the technical variants (e.g. `FormatImplementor` interface with
  `NTFSImplementor` / `FAT32Implementor`) — what actually talks to the technical layer.
- Don't confuse this with **Adapter**: Adapter is a one-off translation of a single pre-existing,
  unmodifiable interface to match what one client expects; Bridge is designed upfront so a whole
  hierarchy of business abstractions can vary independently from a whole hierarchy of technical
  implementations (e.g. NTFS/FAT32 as interchangeable disk-format implementors behind a single
  `LogicalUnit` abstraction).

**Structural signature**

| | |
|-|-|
| Min classes | 4 — Abstraction, RefinedAbstraction, Implementor, ConcreteImplementor |
| Relationship types | `inheritance`, `composition` |
| Key methods | `operation`, `operationimpl` |

---

### Composite
Use Composite when you want to:
- Represent a hierarchy of objects.
- Ignore the difference between a simple component and a component that contains others (uniform interface).

**Mandatory roles — always include all three:**
- **Component** (abstract class or interface): declares the common interface for both leaves and composites; name it after the domain concept (e.g. `FileSystemEntry`, `Entry`, `Node`).
- **Leaf** (concrete class, cannot contain children): the indivisible element of the hierarchy (e.g. `File`, `Document`, `Item`); must implement the Component interface.
- **Composite** (concrete class, contains children): the container that can hold other Components (e.g. `Folder`, `Directory`, `Group`); holds a `List<Component>` and delegates `operation()` to each child.

**Naming guidance for domain models:**
- Name classes after domain concepts, not after the pattern roles (prefer `File` over `Leaf`, `Folder` over `Composite`).
- Always include an explicit collection attribute on the Composite (e.g. `- children: List<FileSystemEntry>`).
- The `operation()` method should be named after the actual domain operation (e.g. `getSize()`, `display()`, `accept()`).

**Structural signature**

| | |
|-|-|
| Min classes | 3 — Component, Leaf, Composite |
| Relationship types | `inheritance`, `composition` |
| Key methods | `add`, `remove`, `operation` |

---

### Decorator
Use Decorator when:
- Responsibilities must be added dynamically and transparently.
- Some responsibilities can be omitted.
- Extensions are independent and it would be impractical to implement them by subclassing.

**Structural signature**

| | |
|-|-|
| Min classes | 3 — Component, ConcreteComponent, Decorator |
| Relationship types | `inheritance`, `composition` |
| Key methods | `operation`, `decorate` |

---

### Facade
Use Facade when you want to:
- Provide a simple interface to a complex system.
- Introduce an interface to decouple the relationships between two complex systems.
- Build the system in layers.

**Structural signature**

| | |
|-|-|
| Min classes | 2 — Facade + at least one subsystem class |
| Relationship types | `association`, `dependency` |
| Key methods | `operation` |

---

### Flyweight
Use Flyweight when:
- A large number of objects are used, and
- Storage costs are high, and
- Object state can be externalised (extrinsic state), and
- Many groups of objects can be replaced by a few shared objects once states are externalised, and
- The application does not depend on object identity.

**Structural signature**

| | |
|-|-|
| Min classes | 3 — Flyweight, ConcreteFlyweight, FlyweightFactory |
| Relationship types | `inheritance`, `composition` |
| Key methods | `operation`, `getflyweight` |

---

### Proxy
Use Proxy when you want to reference an object in a more complex way than a simple pointer:
- **Remote proxy**: ambassador for a remote object.
- **Protection proxy**: access control.
- **Smart reference**: persistence, reference counting, etc.

**Structural signature**

| | |
|-|-|
| Min classes | 3 — Subject, RealSubject, Proxy |
| Relationship types | `inheritance`, `association` |
| Key methods | `request` |

---

## Behavioural Patterns

### ChainOfResponsibility
Use ChainOfResponsibility when:
- More than one object can handle a request, and the handler is not known a priori.
- The set of objects that can handle a request is built dynamically.

**Structural signature**

| | |
|-|-|
| Min classes | 2 — Handler, ConcreteHandler(s) |
| Relationship types | `inheritance`, `association` |
| Key methods | `handle`, `setnext` |

---

### Command
Use Command when:
- You need to specify, store, and execute actions at different points in time.
- You want to support undo; executed commands and the affected objects' states can be stored.
- You want to implement transactions (high-level actions).

**Structural signature**

| | |
|-|-|
| Min classes | 4 — Command, ConcreteCommand, Invoker, Receiver |
| Relationship types | `inheritance`, `association` |
| Key methods | `execute`, `undo` |

---

### Interpreter
Use Interpreter when a language must be interpreted and:
- The grammar is simple.
- Efficiency is not a critical parameter.

**Structural signature**

| | |
|-|-|
| Min classes | 3 — AbstractExpression, TerminalExpression, NonTerminalExpression |
| Relationship types | `inheritance` |
| Key methods | `interpret` |

---

### Iterator
Use Iterator when:
- You need to access a composite object without exposing its internal structure.
- You want to offer multiple ways to traverse a composite structure.
- You want to provide a uniform interface for traversing different structures.

**Structural signature**

| | |
|-|-|
| Min classes | 4 — Iterator, ConcreteIterator, Aggregate, ConcreteAggregate |
| Relationship types | `inheritance`, `association` |
| Key methods | `next`, `hasnext`, `createiterator` |

---

### Mediator
Use Mediator when:
- Many objects must communicate with each other.
- Reusing an object is difficult because it references and communicates with many other objects.

**Structural signature**

| | |
|-|-|
| Min classes | 3 — Mediator, ConcreteMediator, Colleague |
| Relationship types | `inheritance`, `association` |
| Key methods | `notify`, `send` |

---

### Memento
Use Memento when:
- You want to save all or part of an object's state in order to restore it later, and
- A direct interface to obtain the object's state would break encapsulation.

**Structural signature**

| | |
|-|-|
| Min classes | 3 — Originator, Memento, Caretaker |
| Relationship types | `association`, `dependency` |
| Key methods | `save`, `restore`, `getstate`, `setstate` |

---

### Observer
Use Observer when:
- An abstraction has multiple dependent aspects; encapsulating them independently allows them to be reused separately.
- A change in one object must be propagated to others.
- An object must notify other objects without knowing who they are.

**Structural signature**

| | |
|-|-|
| Min classes | 3 — Subject, ConcreteSubject, Observer (+ ConcreteObserver) |
| Relationship types | `inheritance`, `association` |
| Key methods | `attach`, `detach`, `notify`, `update` |

---

### State
Use State when:
- The behaviour of an object depends on its state, which changes at runtime.
- Operations contain large conditional statements (switch/case) that depend on the object's state.

**Structural signature**

| | |
|-|-|
| Min classes | 3 — Context, State, ConcreteState |
| Relationship types | `inheritance`, `composition` |
| Key methods | `handle`, `setstate`, `request` |

---

### Strategy
Use Strategy when:
- Many related classes differ only in their behaviour; Strategy provides a way to configure a class with one of several behaviours.
- Multiple variants of an algorithm are needed.
- An algorithm uses data that clients should not know about.

**Structural signature**

| | |
|-|-|
| Min classes | 3 — Context, Strategy, ConcreteStrategy |
| Relationship types | `inheritance`, `composition` |
| Key methods | `execute`, `setstrategy` |

---

### TemplateMethod
Use TemplateMethod:
- To implement the invariant part of an algorithm.
- To share common behaviour across a class hierarchy.
- To control extensions in subclasses.

**Structural signature**

| | |
|-|-|
| Min classes | 2 — AbstractClass, ConcreteClass |
| Relationship types | `inheritance` |
| Key methods | `templatemethod`, `primitiveoperation` |

---

### Visitor
Use Visitor when:
- An object structure contains many classes with different interfaces and you want to apply diverse operations on these objects.
- The structures are stable but the operations on their objects are likely to evolve.

**Structural signature**

| | |
|-|-|
| Min classes | 4 — Visitor, ConcreteVisitor, Element, ConcreteElement |
| Relationship types | `inheritance`, `dependency` |
| Key methods | `visit`, `accept` |

---

## Combination Rules

Rules for diagrams that combine two GoF patterns. Each rule identifies the **pivot class** that bridges both patterns and the **mandatory relationships** that must connect them.

### Command+Memento
Integration rule: the ConcreteCommand holds a Memento of the Receiver's state to support undo.
- `execute()` saves the Receiver's current state as a Memento before acting.
- `undo()` restores the Receiver's state from the stored Memento.
- The Caretaker (or the Invoker) manages the Memento history.

Mandatory relationships:
- `association` or `composition` from ConcreteCommand to Memento (label: "savedState")
- `association` from ConcreteCommand to Receiver

---

### Composite+Singleton
Integration rule: the Singleton provides the unique entry point to the root of the Composite hierarchy.
- The Singleton class holds a reference to the root Component.
- Clients access the hierarchy exclusively through the Singleton.

Mandatory relationships:
- `association` from Singleton to Component (label: "root")

---

### Composite+Strategy
Integration rule: a Context class uses both a Composite structure and a Strategy algorithm.
- The Strategy operates on Component nodes (e.g., computes a value recursively across the hierarchy).
- The Context holds the root Component and delegates the algorithm to the Strategy.

Mandatory relationships:
- `association` from Context to Component (label: "root")
- `composition` or `association` from Context to Strategy

---

### Memento+Observer
Integration rule: the **same class** plays both the Originator (Memento) and the Subject (Observer) roles.
This pivot class (e.g., Document, Editor) must expose both interfaces on a single class:
- Memento side: `createMemento(): Memento`, `restore(m: Memento): void`
- Observer side: `attach(o: Observer): void`, `detach(o: Observer): void`, `notify(): void`

The pivot class must NOT be split into two separate classes. All six methods above belong to the same class.

Mandatory relationships:
- `association` from pivot class to Observer interface (label: "observers") — the Subject holds its subscriber list
- `composition` from Caretaker to Memento (label: "history")
- `association` from Caretaker to pivot class
