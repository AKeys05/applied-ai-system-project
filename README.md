# PetPlanify (AI System Final Project)

## Original Project - PawPal+

This system is an extension of the Module 2 Project: PawPal+. Its original goals was to create a Streamlit application that helps a pet owner plan and manage caretaking tasks for their pets. It allows users to enter their pets' basic information, add/edit tasks, and generate a daily schedule based on their inputted constraints and preferences.  


## Summary

PetPlanify is an AI-assisted pet care scheduling app that uses owner preferences and pet profiles to create an optimized daily schedule. This system is for the user that needs help coordinating their routine due to various factors like owning multiple pets of different breeds, having limited availability, and juggling competing task priorities.    


## Architecture Overview

The core system operates at a three-layer pipeline:  

1. Users input their pet information and task preferences.  

- This includes their pet's names, species, breeds, energy level, age and number of walks, meals, medication does, grooming sessions, and play times a day/week.  

2. Retrieval Augmented Generation (RAG) is used as a guidance mechanism for routine building according to a breed knowledge base.  

- Owner/pet profiles and the RAG-enhanced tasks feed a Groq LlaMA call that assigns globally optimal times. 

- A bitmap fallback and conflict resolution pass clean up anything the AI does not handle.  

3. Tasks are assigned and validated into a complete optimized schedule for the user's review.  

- Users have the opportunity to set, review and confirm each task before it is fed to the scheduler.  

- Finalized routines offer a daily and weekly view along with evaluation metrics. 


## Setup Instructions

1. Clone the repo and create a virtual environment. 

2. Install dependencies: `pip install -r requirements.txt`. 

3. Configure a Groq API key and paste a .streamlit/secrets.toml fil: `GROQ_API_KEY="your_key_here"`. 

4. Run the app: `streamlit run app.py`. 

5. Run the evaluation script to verify guardrails: `python eval/evaluate_phase1.py`. 


## Sample Interactions

### 1. Single-pet, high-energy routine

Owner: Ashley  
Pet: Poppy (French Bulldog, 1yo, high activity)  
- 3 walks  
- 3 play sessions  
- 1 grooming  
- 3 meals  


### 2. Multi-pet routine

Owner: Alex  
Pets:  
- Biscuit (Great Dane, 5yo, low activity)  
  - 3 walks (7AM - 7PM)  
  - 2 meals (7AM - 7PM)  
  - 1 medication (locked at 8AM)  
- Mochi (Ragdoll, 2yo, medium activity)  
  - 0 walks  
  - 2 meals (7AM - 7PM)  
  - 1 medication (locked at 8AM)  
  - 1 grooming (flexible)  


## Design Decisions

**Groq over Gemini/Claude:** Groq's free LLaMa 3.3 tier supports native JSON mode, returns responses in under two seconds and has no per-token cost at the usage level. Compared to issues with cost and request limit of Gemini and Claude, Groq presented itself to be the most practical and optimal tool for making scheduling generation calls.  

**Soft preferred times over hard constraints:** The AI planner treats preferred times as soft hints rather than immovable anchors. This allows for routines with multiple daily walks and meals to be evenly and flexibly spaced across 12-hour windows. Hard-locking all generated tasks would cause frequent unschedulable conflicts. Those that still want strict timing can opt in to using the explicit lock function in Step 2 of the review workflow.  

**Bitmap fallback:** After the AI planner assigns time, each assignment is validated against the owner's availability window and task's own time constraint before being accepted and finalized. Any assignment that fails validation, or is unable to be verified with Groq, has a nearest-target greedy search performed on it. This allows the system to be functional even without an API key.  

**Confidence scoring:** Each scheduled task gets floating-point confidence score starting at 1.0, and is deducted for conditions that apply certainty such as RAG guidance, time constraints applied, owner availability applied, etc. Tasks below 0.6 trigger a guardrail warning. The overall confidence is the mean across all scheduled tasks. This gives the scheduler a graded signal rather than a pass/fail - helping users to understand which specific tasks led to uncertainty.  

## Testing Summary

### What Worked

- The tests presented in the `evaluate_phase1.py` file consistently pass all 4 scenarios across runs, even with the bitmap fallback.  
- The guardrail demos are able to reliably trigger the expected warnings and unscheduled outputs.   
- For dogs and cats breeds within the knowledge base, RAG citation coverage hits 1.00.

### What Didn't Work

- The AI planner is non-deterministic so the same input can produce different time assignments across different sessions.

### What I Learned

- LLM prompts require explicit ordering rules and hints in the message body for it to properly rationalize.
- Pre-computing soft preferred times in the data model was more reliable than expecting the AI to infer even distribution on its own.

## Reflection

AI was used in a multitude of ways throughout each step of the design, implementation, testing, and debugging process. At the beginning of the project, I was stuck on coming up with ideas for implementing the new required AI feature into the PawPal+ system. I used CoPilot to help me generate some potential ideas for using RAG or an agentic workflow, and worked from there. After determining that I want my system to focus on the use of RAG to incorporate specific breed-based knowledge in creating the schedules, I then used the agent's Plan Mode help detail steps for implementation. Implementation was the key stage that required critical human oversight of the suggestions and changes the agent was producing. For example, one helpful suggestion was allowing users to input a set amount of daily/weekly meals, walks, play times, and medication doses, and implement a routine builder to do the rest. This is incredibly less tedious than having users input each individual task. However, there were also a variety of not-so-helpful suggestions, mainly pertaining to the system's UI. For example, the agent was listing every feature and task one-by-one on a single page, creating an unreasonably long list of material for the user to have to scroll through. That is when I made the decision to implement pages to improve the end-to-end workflow. Another notable aspect to reflect on throughout this design phase is the difference in agents. I experienced that Claude was better in generating coherent code snippets while Copilot was better with generating plans. For the future, the system can benefit from the following improvements:
- persistent schedule history and completion tracking
- calendar and notification export
- an expanded and dynamically-sourced knowledge base
- multi-owner support
- feedback loop implemented into the prompt
- AI planning by passing the full week's tasks instead of each independent day




