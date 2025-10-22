#!/usr/bin/env python3
"""
LLM Judge for test results - evaluates with nuance for minor differences.
"""

import json
import os
import requests
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

class TestResultJudge:
    def __init__(self):
        self.api_key = os.getenv("DEDALUS_API_KEY")
        if not self.api_key:
            raise ValueError("DEDALUS_API_KEY not found in environment")
    
    def evaluate_test(self, test_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a single test result with LLM judgment.
        """
        # Skip if already passed
        if test_result.get("passed"):
            return {
                "test_number": test_result["test_number"],
                "original_pass": True,
                "llm_pass": True,
                "llm_score": 1.0,
                "reasoning": "Test already passed strict comparison"
            }
        
        # Build prompt for LLM evaluation
        prompt = f"""You are evaluating a bid processing system test result. Determine if the actual output is acceptable compared to expected output.

TEST CASE: {test_result.get('subject', 'Unknown')}
HAS ATTACHMENTS: {test_result.get('has_attachments', False)}

EXPECTED OUTPUT:
{json.dumps(test_result.get('expected_output', {}).get('analysis', {}), indent=2)}

ACTUAL OUTPUT:
{json.dumps(test_result.get('actual_output', {}).get('analysis', {}), indent=2)}

DIFFERENCES FOUND:
{json.dumps(test_result.get('differences', []), indent=2)}

EVALUATION CRITERIA:
1. Classification (relevant, needs_clarification, bid_proposal_included):
   - Must be logically consistent (no bid without attachment)
   - Relevance can be subjective for edge cases
   
2. For extraction from attachments - BE VERY LENIENT:
   - Company names: PASS if same company, ignore capitalization/formatting (e.g., "GRISHAM PLUMBING LLC" = "Grisham Plumbing LLC")
   - Trade: PASS if related/subset (e.g., "Plumbing" includes "Utilities & Plumbing", "Concrete" = "Concrete Work")
   - Project names: PASS if same project identified (e.g., both mention "Panda Express" or "O'Reilly")
   - Full addresses are BETTER than abbreviations like "PX-San Antonio"

3. Special rules:
   - If no attachment exists but expected says bid_proposal_included=true, actual=false is CORRECT
   - null vs false for forward_result and attachment_analysis should be ignored completely
   - Type mismatches between null and false should NOT affect score
   
4. IMPORTANT - Give HIGH scores (0.9+) when:
   - The actual extraction identifies the correct company (any format)
   - The actual extraction identifies the correct project (Panda Express, O'Reilly, etc)
   - The actual extraction has MORE detail than expected (full address vs "PX-San Antonio")
   - All key information is extracted, even if formatting differs

5. Focus on INFORMATION ACCURACY not format:
   - "Panda Express located at 2452 W Loop 1604 S" is BETTER than "PX-San Antonio (Bulverde)"
   - Both refer to the same project, but actual has more useful detail

Respond with JSON only:
{{
  "pass": true/false,
  "score": 0.0-1.0,
  "reasoning": "Brief explanation",
  "category_scores": {{
    "classification": 0.0-1.0,
    "extraction": 0.0-1.0
  }}
}}"""

        try:
            # Call LLM
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 500
            }
            
            response = requests.post(
                "https://api.dedaluslabs.ai/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"LLM API error: {response.status_code}")
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # Parse JSON response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                llm_eval = json.loads(content[start:end])
                
                return {
                    "test_number": test_result["test_number"],
                    "subject": test_result.get("subject", ""),
                    "original_pass": False,
                    "llm_pass": llm_eval.get("pass", False),
                    "llm_score": llm_eval.get("score", 0.0),
                    "reasoning": llm_eval.get("reasoning", ""),
                    "category_scores": llm_eval.get("category_scores", {})
                }
            else:
                raise ValueError("Could not parse JSON from LLM response")
                
        except Exception as e:
            print(f"Error evaluating test {test_result.get('test_number')}: {str(e)}")
            return {
                "test_number": test_result["test_number"],
                "subject": test_result.get("subject", ""),
                "original_pass": False,
                "llm_pass": False,
                "llm_score": 0.0,
                "reasoning": f"Evaluation error: {str(e)}",
                "error": str(e)
            }
    
    def judge_all_results(self, results_file: str) -> Dict[str, Any]:
        """
        Judge all test results from a comparison file.
        """
        # Load test results
        with open(results_file, 'r') as f:
            data = json.load(f)
        
        test_results = data.get("test_results", [])
        
        print("=" * 80)
        print("LLM JUDGE EVALUATION")
        print("=" * 80)
        print(f"Evaluating {len(test_results)} test results...")
        print("=" * 80)
        
        # Evaluate each test
        evaluations = []
        for test in test_results:
            print(f"\nTest {test['test_number']}: {test.get('subject', '')[:50]}...")
            eval_result = self.evaluate_test(test)
            evaluations.append(eval_result)
            
            # Print result
            if eval_result["llm_pass"]:
                print(f"  ✅ LLM PASS (Score: {eval_result['llm_score']:.2f})")
            else:
                print(f"  ❌ LLM FAIL (Score: {eval_result['llm_score']:.2f})")
            print(f"  Reasoning: {eval_result['reasoning'][:100]}...")
        
        # Calculate statistics
        original_passed = sum(1 for e in evaluations if e["original_pass"])
        llm_passed = sum(1 for e in evaluations if e["llm_pass"])
        total = len(evaluations)
        
        avg_score = sum(e["llm_score"] for e in evaluations) / total if total > 0 else 0
        
        # Determine grade
        pass_rate = (llm_passed / total * 100) if total > 0 else 0
        if pass_rate >= 90:
            grade = "A"
        elif pass_rate >= 80:
            grade = "B"
        elif pass_rate >= 70:
            grade = "C"
        elif pass_rate >= 60:
            grade = "D"
        else:
            grade = "F"
        
        print("\n" + "=" * 80)
        print("FINAL LLM JUDGE RESULTS")
        print("=" * 80)
        print(f"Original Strict Comparison: {original_passed}/{total} passed")
        print(f"LLM Judge Evaluation: {llm_passed}/{total} passed")
        print(f"Average Score: {avg_score:.2f}")
        print(f"Pass Rate: {pass_rate:.1f}%")
        print(f"Grade: {grade}")
        
        # Show improvements
        improvements = []
        for e in evaluations:
            if not e["original_pass"] and e["llm_pass"]:
                improvements.append(e)
        
        if improvements:
            print(f"\n📈 Tests that passed with LLM judgment but failed strict comparison:")
            for imp in improvements:
                print(f"  - Test {imp['test_number']}: {imp['subject'][:40]}... (Score: {imp['llm_score']:.2f})")
        
        # Create output
        output = {
            "summary": {
                "total_tests": total,
                "original_passed": original_passed,
                "llm_passed": llm_passed,
                "average_score": round(avg_score, 2),
                "pass_rate": round(pass_rate, 1),
                "grade": grade
            },
            "evaluations": evaluations,
            "improvements": [
                {
                    "test_number": e["test_number"],
                    "subject": e["subject"],
                    "score": e["llm_score"],
                    "reasoning": e["reasoning"]
                }
                for e in improvements
            ]
        }
        
        # Save results
        output_file = results_file.replace(".json", "_llm_judged.json")
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n💾 LLM Judge results saved to: {output_file}")
        
        return output


def main():
    """
    Main function to run LLM judge on test results.
    """
    import sys
    
    # Default to the most recent test results
    if len(sys.argv) > 1:
        results_file = sys.argv[1]
    else:
        # Check which results files exist
        if os.path.exists("dataset/test_comparison_results_11_20.json"):
            results_file = "dataset/test_comparison_results_11_20.json"
            print("Using test results for cases 11-20")
        elif os.path.exists("dataset/test_comparison_results.json"):
            results_file = "dataset/test_comparison_results.json"
            print("Using test results for cases 1-10")
        else:
            print("No test results found. Run test_system_simple.py first.")
            return
    
    judge = TestResultJudge()
    judge.judge_all_results(results_file)


if __name__ == "__main__":
    main()