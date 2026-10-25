we want to make a coding agent in python which can solve simple bugs
we will use grok llm for this ... see in the past files and we will use the same

the llm will have some tools which will help in solving the bug
One tool can be search files which list path of files which are related to the bug as per the llm
we need search in file which can give line numbers related to the bug
we need replace which will replacing the line with the another line

i want to test this myself.prepare a simple .java file and write boiler plate in it .. do not introduce any bug now
i will introduce the bug and test it myself

i want to give the bug in simple english in cli and the llm and the tools should solve it
make a system without langgraph and keep it simple
Also there will be max retry of 3 times ... if the llm cant solve inside this limit it shld print a message saying that it cannot solve the bug

also there should be clear statements saying which tool was called at each step we want to understand the flow completely
as soon as i change the java file and run the agent it shld me my bug after i give my bug .. it shld begin solving it

do not write any test cases for now
if anything is unclear ask me.
