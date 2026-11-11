from agent_llm.llm import call_llm

print("Start")
raw,cpu_seconds  = call_llm("hello",local=True)
print(raw)
print("duration",cpu_seconds)
