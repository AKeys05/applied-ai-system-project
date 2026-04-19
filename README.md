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

**Groq over Gemini/Claude:** 

**Soft preferred times over hard constraints:**

**Bitmap fallback:**

**Confidence scoring:**

## Testing Summary

### What Worked

### What Didn't Work

### What I Learned



## Reflection





