
import itertools
import os
import csv
from datetime import datetime

# Define the arguments and their possible values for the experiments
EXPERIMENTS = {
    '--P': [8],
    '--R': [1],
    '--method': ['ror'],
    '--metric': ['hellinger'],
    '--blur': [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0],
    '--ltp': [True],
    '--crop-seed': [1, 42, 35, 99, 123, 2024, 777, 888, 999, 1111],
}

# Fixed arguments
FOLDER = r"LBP_Test_Images/Swatches/LBP_Texture_Swatches"
X = 64
Y = 64

# Output log file
LOG_DIR = "results"
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"experiment_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

# Prepare all combinations
keys = list(EXPERIMENTS.keys())
values = list(EXPERIMENTS.values())
combinations = list(itertools.product(*values))

with open(log_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    header = keys + [
        'correct_matches', 'total', 'pct_correct',
        'highest_correct', 'lowest_correct', 'highest_incorrect', 'lowest_incorrect',
        'csv_file', 'results_json_file'
    ]
    writer.writerow(header)
    # Try to import the main entry point for direct results
    try:
        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))
        from automated_lbp_benchmarking.main import main as lbp_main
        use_direct = True
    except Exception as import_exc:
        print(f"[WARNING] Could not import main programmatically, falling back to subprocess: {import_exc}")
        use_direct = False

    for combo in combinations:
        args = []
        for k, v in zip(keys, combo):
            if isinstance(v, bool):
                if v:
                    args.append(k)
            else:
                args.extend([k, str(v)])
        args.extend(["--X", str(X), "--Y", str(Y)])
        csv_name = f"exp_{'_'.join(str(x) for x in combo)}.csv"
        args.append(f"--save-csv={csv_name}")
        args = [str(a) for a in args]
        results_json_file = os.path.join(LOG_DIR, f"{os.path.splitext(csv_name)[0]}_results.json")
        row = list(combo)
        if use_direct:
            # Use direct Python call
            cli_args = [FOLDER] + args
            try:
                import os
                os.environ["LBP_EXPERIMENT_MODE"] = "1"
                results = lbp_main(return_results=True, cli_args=cli_args)
                row += [
                    results.get('correct_matches'),
                    results.get('total'),
                    results.get('pct_correct'),
                    results.get('highest_correct'),
                    results.get('lowest_correct'),
                    results.get('highest_incorrect'),
                    results.get('lowest_incorrect'),
                    csv_name,
                    os.path.basename(results_json_file)
                ]
            except Exception as e:
                print(f"Experiment failed (direct): {e}")
                row += ["ERROR"] * 8 + [csv_name, ""]
        else:
            # Fallback to subprocess
            import subprocess
            import json
            cmd = ["python", "run.py", FOLDER] + args
            print(f"Running: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                if os.path.exists(results_json_file):
                    with open(results_json_file, 'r', encoding='utf-8') as jf:
                        results = json.load(jf)
                    row += [
                        results.get('correct_matches'),
                        results.get('total'),
                        results.get('pct_correct'),
                        results.get('highest_correct'),
                        results.get('lowest_correct'),
                        results.get('highest_incorrect'),
                        results.get('lowest_incorrect'),
                        csv_name,
                        os.path.basename(results_json_file)
                    ]
                else:
                    row += ["ERROR"] * 8 + [csv_name, ""]
            except Exception as e:
                print(f"Experiment failed (subprocess): {e}")
                row += ["ERROR"] * 8 + [csv_name, ""]
        writer.writerow(row)
        f.flush()
print(f"All experiments complete. Log saved to {log_file}")
