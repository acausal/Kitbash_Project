#!/usr/bin/env python3
"""
Redis and Kitbash Testing Script for Windows
============================================

This script:
1. Verifies Redis is running
2. Checks Python dependencies
3. Runs Phase 3B tests
4. Provides troubleshooting info

Run this on your Windows machine in PowerShell:
    python redis_test_windows.py
"""

import subprocess
import sys
import json
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and return (success, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            timeout=5
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Timeout running: {description}"
    except Exception as e:
        return False, "", str(e)

def check_redis():
    """Check if Redis is running"""
    print("\n" + "="*60)
    print("STEP 1: Checking Redis Server")
    print("="*60)
    
    success, stdout, stderr = run_command("redis-cli ping", "Redis ping")
    
    if success and "PONG" in stdout:
        print("✅ Redis is running and responding")
        
        # Get server info
        success, info, _ = run_command("redis-cli info server", "Redis info")
        if success:
            print(f"   Redis response: {stdout.strip()}")
        return True
    else:
        print("❌ Redis is NOT responding")
        print(f"   Error: {stderr}")
        print("\n   Fix: Start Redis from Windows Services or use:")
        print("   redis-server.exe --service-run")
        return False

def check_python_deps():
    """Check if required Python packages are installed"""
    print("\n" + "="*60)
    print("STEP 2: Checking Python Dependencies")
    print("="*60)
    
    required = [
        ("redis", "Redis Python client"),
        ("fastapi", "FastAPI web framework"),
        ("uvicorn", "ASGI server"),
        ("pydantic", "Data validation"),
    ]
    
    missing = []
    for package, description in required:
        try:
            __import__(package)
            print(f"✅ {package:<20} ({description})")
        except ImportError:
            print(f"❌ {package:<20} ({description}) - MISSING")
            missing.append(package)
    
    if missing:
        print(f"\n   Install missing packages with:")
        print(f"   pip install {' '.join(missing)}")
        return False
    return True

def check_kitbash_repo():
    """Check if Kitbash repo is accessible"""
    print("\n" + "="*60)
    print("STEP 3: Checking Kitbash Repository")
    print("="*60)
    
    # Check current directory for repo
    repo_paths = [
        Path.cwd() / "Kitbash_Project",
        Path.home() / "Kitbash_Project",
        Path.cwd() / "..",
        Path.cwd().parent / "Kitbash_Project",
    ]
    
    for repo_path in repo_paths:
        if (repo_path / "src" / "redis_spotlight.py").exists():
            print(f"✅ Found Kitbash repo at: {repo_path}")
            
            # Check key files
            key_files = [
                "src/redis_spotlight.py",
                "src/test_redis_spotlight.py",
                "src/kitbash_redis_schema.py",
            ]
            
            for file in key_files:
                file_path = repo_path / file
                if file_path.exists():
                    print(f"   ✅ {file} ({file_path.stat().st_size} bytes)")
                else:
                    print(f"   ⚠️  {file} NOT found")
            
            return str(repo_path)
    
    print("❌ Could not find Kitbash repo")
    print(f"   Searched paths: {[str(p) for p in repo_paths]}")
    return None

def run_redis_tests(repo_path):
    """Run Redis spotlight tests"""
    print("\n" + "="*60)
    print("STEP 4: Running Redis Spotlight Tests")
    print("="*60)
    
    test_file = Path(repo_path) / "src" / "test_redis_spotlight.py"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    print(f"Running: {test_file}")
    print("-" * 60)
    
    # Try with pytest first
    success, stdout, stderr = run_command(
        f"pytest {test_file} -v",
        "pytest"
    )
    
    if success:
        print("✅ Tests passed with pytest")
        print(stdout)
        return True
    else:
        # Fallback: run with python directly
        print("⚠️  pytest not available, trying direct execution...")
        success, stdout, stderr = run_command(
            f"python {test_file}",
            "direct execution"
        )
        
        if success:
            print("✅ Tests passed with direct execution")
            print(stdout)
            return True
        else:
            print("❌ Tests failed")
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            return False

def main():
    """Main test suite"""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║   Kitbash Phase 3B.1 - Redis Spotlight Test Suite         ║")
    print("║   Windows Verification Script                             ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    results = {
        "redis_running": check_redis(),
        "python_deps": check_python_deps(),
        "kitbash_repo": check_kitbash_repo(),
    }
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if results["redis_running"]:
        print("✅ Redis: Running")
    else:
        print("❌ Redis: NOT running - start it first")
    
    if results["python_deps"]:
        print("✅ Python dependencies: All installed")
    else:
        print("❌ Python dependencies: Some missing - install with pip")
    
    if results["kitbash_repo"]:
        print(f"✅ Kitbash repo: Found at {results['kitbash_repo']}")
        
        # Try running tests
        print("\nRunning tests...")
        run_redis_tests(results["kitbash_repo"])
    else:
        print("❌ Kitbash repo: Not found")
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("""
1. If Redis is NOT running:
   - Open Windows Services (services.msc)
   - Find 'Redis' service
   - Right-click → Start
   - Or use: redis-server.exe --service-run

2. If Python dependencies are missing:
   - pip install redis fastapi uvicorn pydantic

3. If Kitbash repo not found:
   - cd to a parent directory containing Kitbash_Project
   - Or git clone https://github.com/acausal/Kitbash_Project

4. Once all checks pass:
   - Run: python -m pytest src/test_redis_spotlight.py -v
   - Or: python src/test_redis_spotlight.py
    """)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
