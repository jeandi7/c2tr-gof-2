# gof/schema.py
#
# Canonical structural schema for the 23 GoF design patterns.
# Used by compute_phi() to evaluate Phi_i as a true structural
# integration score rather than a raw element count.
#
# Each entry defines:
#   min_classes       : minimum number of classes expected in the pattern
#   expected_rel_types: set of relationship types canonical to the pattern
#   key_methods       : lowercase fragments expected in generated method signatures

GOF_SCHEMA: dict[str, dict] = {

    # ── Creational ──────────────────────────────────────────────────────────────

    "Singleton": {
        "min_classes": 1,
        "expected_rel_types": set(),
        "key_methods": ["getinstance"],
    },
    "FactoryMethod": {
        "min_classes": 3,                          # Creator, ConcreteCreator, Product
        "expected_rel_types": {"inheritance", "dependency"},
        "key_methods": ["factorymethod", "create"],
    },
    "AbstractFactory": {
        "min_classes": 4,                          # AbstractFactory, ConcreteFactory, AbstractProduct, ConcreteProduct
        "expected_rel_types": {"inheritance", "dependency"},
        "key_methods": ["createproduct", "create"],
    },
    "Builder": {
        "min_classes": 3,                          # Builder, ConcreteBuilder, Director
        "expected_rel_types": {"association", "dependency"},
        "key_methods": ["build", "getresult", "construct"],
    },
    "Prototype": {
        "min_classes": 2,                          # Prototype, ConcretePrototype
        "expected_rel_types": {"inheritance"},
        "key_methods": ["clone"],
    },

    # ── Structural ───────────────────────────────────────────────────────────────

    "Adapter": {
        "min_classes": 3,                          # Target, Adapter, Adaptee
        "expected_rel_types": {"inheritance", "association"},
        "key_methods": ["request", "specificrequest"],
    },
    "Bridge": {
        "min_classes": 4,                          # Abstraction, RefinedAbstraction, Implementor, ConcreteImplementor
        "expected_rel_types": {"inheritance", "composition"},
        "key_methods": ["operation", "operationimpl"],
    },
    "Composite": {
        "min_classes": 3,                          # Component, Leaf, Composite
        "expected_rel_types": {"inheritance", "composition"},
        "key_methods": ["add", "remove", "operation"],
    },
    "Decorator": {
        "min_classes": 3,                          # Component, ConcreteComponent, Decorator
        "expected_rel_types": {"inheritance", "composition"},
        "key_methods": ["operation", "decorate"],
    },
    "Facade": {
        "min_classes": 2,                          # Facade + at least one subsystem class
        "expected_rel_types": {"association", "dependency"},
        "key_methods": ["operation"],
    },
    "Flyweight": {
        "min_classes": 3,                          # Flyweight, ConcreteFlyweight, FlyweightFactory
        "expected_rel_types": {"inheritance", "composition"},
        "key_methods": ["operation", "getflyweight"],
    },
    "Proxy": {
        "min_classes": 3,                          # Subject, RealSubject, Proxy
        "expected_rel_types": {"inheritance", "association"},
        "key_methods": ["request"],
    },

    # ── Behavioural ──────────────────────────────────────────────────────────────

    "ChainOfResponsibility": {
        "min_classes": 2,                          # Handler, ConcreteHandler(s)
        "expected_rel_types": {"inheritance", "association"},
        "key_methods": ["handle", "setnext"],
    },
    "Command": {
        "min_classes": 4,                          # Command, ConcreteCommand, Invoker, Receiver
        "expected_rel_types": {"inheritance", "association"},
        "key_methods": ["execute", "undo"],
    },
    "Interpreter": {
        "min_classes": 3,                          # AbstractExpression, TerminalExpression, NonTerminalExpression
        "expected_rel_types": {"inheritance"},
        "key_methods": ["interpret"],
    },
    "Iterator": {
        "min_classes": 4,                          # Iterator, ConcreteIterator, Aggregate, ConcreteAggregate
        "expected_rel_types": {"inheritance", "association"},
        "key_methods": ["next", "hasnext", "createiterator"],
    },
    "Mediator": {
        "min_classes": 3,                          # Mediator, ConcreteMediator, Colleague
        "expected_rel_types": {"inheritance", "association"},
        "key_methods": ["notify", "send"],
    },
    "Memento": {
        "min_classes": 3,                          # Originator, Memento, Caretaker
        "expected_rel_types": {"association", "dependency"},
        "key_methods": ["save", "restore", "getstate", "setstate"],
    },
    "Observer": {
        "min_classes": 3,                          # Subject, ConcreteSubject, Observer, ConcreteObserver
        "expected_rel_types": {"inheritance", "association"},
        "key_methods": ["attach", "detach", "notify", "update"],
    },
    "State": {
        "min_classes": 3,                          # Context, State, ConcreteState
        "expected_rel_types": {"inheritance", "composition"},
        "key_methods": ["handle", "setstate", "request"],
    },
    "Strategy": {
        "min_classes": 3,                          # Context, Strategy, ConcreteStrategy
        "expected_rel_types": {"inheritance", "composition"},
        "key_methods": ["execute", "setstrategy"],
    },
    "TemplateMethod": {
        "min_classes": 2,                          # AbstractClass, ConcreteClass
        "expected_rel_types": {"inheritance"},
        "key_methods": ["templatemethod", "primitiveoperation"],
    },
    "Visitor": {
        "min_classes": 4,                          # Visitor, ConcreteVisitor, Element, ConcreteElement
        "expected_rel_types": {"inheritance", "dependency"},
        "key_methods": ["visit", "accept"],
    },

}
