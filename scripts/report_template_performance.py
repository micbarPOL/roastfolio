import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
import roast_tracking

def main():
    print("Generating Template Performance Report (Last 30 Days)...")
    try:
        report = roast_tracking.get_template_report(days=30)
    except Exception as e:
        print(f"Failed to generate report: {e}")
        return

    print(f"\nAnalyzed {len(report['templates'])} active templates.")
    
    candidates = report.get("disable_candidates", [])
    if not candidates:
        print("\n✅ No templates currently meet the disabling criteria (high negative rate or highly repetitive).")
    else:
        print(f"\n⚠️ FOUND {len(candidates)} TEMPLATES TO POTENTIALLY DISABLE:")
        for idx, cand in enumerate(candidates, 1):
            tid = cand["templateId"]
            reason = cand["reason"]
            stats = cand["stats"]
            print(f"\n  {idx}. Template: {tid}")
            print(f"     Reason: {reason}")
            print(f"     Displays: {stats['displayCount']} | Negative Rate: {stats['negativeRate']*100:.1f}% | Positive Rate: {stats['positiveRate']*100:.1f}%")
            print(f"     Repetitive Reports: {stats['repetitiveCount']} | Too Harsh: {stats['tooHarshCount']}")
            
    print("\nScenarios Summary:")
    scen_sorted = sorted(report["scenarios"].items(), key=lambda x: x[1]["displayed"], reverse=True)
    for scen, stats in scen_sorted:
        disp = stats["displayed"]
        print(f"  - {scen}: {disp} displays, {stats['positive']} pos, {stats['negative']} neg")
        
    print("\nReport complete.")

if __name__ == "__main__":
    main()
