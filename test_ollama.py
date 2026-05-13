import sys
import os

# Add the project directory to sys.path
sys.path.append('/Users/poerking/Downloads/BuscaChambas3mill-main')

from brain import evaluate_vacancy_pro

test_job = {
    "title": "Senior Android Developer",
    "description": "We are looking for an expert in Kotlin, Jetpack Compose, and Clean Architecture to join our team at a major retail company."
}

print("Testing evaluate_vacancy_pro with Ollama...")
result = evaluate_vacancy_pro(test_job)
print("\nResult:")
print(result)
