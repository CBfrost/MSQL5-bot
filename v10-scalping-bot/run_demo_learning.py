#!/usr/bin/env python3
"""
V10 Scalping Bot - Demo Learning Mode
Safe demo trading with adaptive learning and automatic graduation assessment
"""

import asyncio
import sys
import time
import webbrowser
import threading
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.main import main
from src.demo_validator import get_demo_validator
from src.adaptive_backtester import get_adaptive_backtester

def print_demo_banner():
    """Print demo learning banner"""
    print("=" * 70)
    print("🎓 V10 SCALPING BOT - DEMO LEARNING MODE")
    print("=" * 70)
    print("🎯 MISSION: Learn and adapt on demo, then graduate to live trading")
    print("")
    print("📚 LEARNING PROCESS:")
    print("   1. 🧪 Demo Trading: Safe testing with virtual money")
    print("   2. 🧠 Adaptive Learning: AI learns from every trade")
    print("   3. ⚙️  Strategy Optimization: Auto-tune parameters")
    print("   4. 📊 Performance Analysis: Track all metrics")
    print("   5. 🎓 Graduation Assessment: Ready for live trading?")
    print("")
    print("🛡️  SAFETY FEATURES:")
    print("   • Demo account validation (no real money at risk)")
    print("   • Comprehensive performance tracking")
    print("   • Automatic strategy optimization")
    print("   • Live trading readiness assessment")
    print("   • Real-time web dashboard monitoring")
    print("")
    print("📈 GRADUATION CRITERIA:")
    print("   • Minimum 7 days of demo trading")
    print("   • 100+ demo trades completed")
    print("   • 55%+ win rate achieved")
    print("   • Positive balance growth (10%+)")
    print("   • Strong risk management (max 10 consecutive losses)")
    print("   • Consistent strategy performance")
    print("")
    print("🌐 DASHBOARD: http://127.0.0.1:8000")
    print("=" * 70)
    print("")

def check_environment_safety():
    """Perform comprehensive environment safety check"""
    print("🔍 PERFORMING SAFETY CHECKS...")
    
    # Get validators
    demo_validator = get_demo_validator()
    
    # Validate demo environment
    validation = demo_validator.validate_demo_environment()
    
    if not validation["is_safe"]:
        print("🚨 CRITICAL SAFETY ISSUES DETECTED!")
        print("❌ Cannot proceed with demo trading:")
        for error in validation["errors"]:
            print(f"   • {error}")
        
        if validation["warnings"]:
            print("\n⚠️  Additional warnings:")
            for warning in validation["warnings"]:
                print(f"   • {warning}")
        
        print("\n🛠️  REQUIRED ACTIONS:")
        print("   1. Switch to a Deriv DEMO account")
        print("   2. Update your .env file with demo API token")
        print("   3. Verify all settings are for demo trading")
        print("\n❌ DEMO LEARNING ABORTED FOR SAFETY")
        return False
    
    # Check for warnings
    if validation["warnings"]:
        print("⚠️  Safety warnings detected:")
        for warning in validation["warnings"]:
            print(f"   • {warning}")
        print("")
    
    # Additional safety warnings
    safety_warnings = demo_validator.get_safety_warnings()
    if safety_warnings:
        print("⚠️  Additional safety considerations:")
        for warning in safety_warnings:
            print(f"   • {warning}")
        print("")
    
    print("✅ SAFETY CHECKS PASSED - Demo environment validated")
    print("✅ Using DEMO account - No real money at risk")
    print("")
    return True

def show_learning_progress():
    """Display current learning progress"""
    try:
        adaptive_backtester = get_adaptive_backtester()
        demo_validator = get_demo_validator()
        
        # Get performance summary
        adaptive_summary = adaptive_backtester.get_performance_summary()
        
        print("📊 CURRENT LEARNING PROGRESS:")
        print(f"   Trades Analyzed: {adaptive_summary.get('total_trades', 0)}")
        print(f"   Overall Win Rate: {adaptive_summary.get('overall_win_rate', 0):.1f}%")
        print(f"   Strategies Tracked: {adaptive_summary.get('total_strategies', 0)}")
        print(f"   Learning Level: {adaptive_summary.get('learning_progress', {}).get('confidence_level', 'Building').title()}")
        
        # Best strategy
        best_strategy = adaptive_summary.get('best_strategy')
        if best_strategy:
            print(f"   Best Strategy: {best_strategy['name']} ({best_strategy['win_rate']:.1f}% win rate)")
        
        # Check graduation status
        graduation = demo_validator.should_graduate_to_live_trading()
        print(f"   Live Trading Readiness: {graduation['confidence_score']:.1%}")
        
        if graduation['ready']:
            print("🎉 READY FOR LIVE TRADING!")
        else:
            print("📚 Continue learning...")
        
        print("")
        
    except Exception as e:
        print(f"⚠️  Could not load learning progress: {e}")
        print("")

def generate_progress_reports():
    """Generate comprehensive progress reports"""
    try:
        print("📋 GENERATING PROGRESS REPORTS...")
        
        adaptive_backtester = get_adaptive_backtester()
        demo_validator = get_demo_validator()
        
        # Generate learning report
        learning_report = asyncio.run(adaptive_backtester.generate_learning_report())
        print("✅ Adaptive learning report generated")
        
        # Generate demo report
        adaptive_summary = adaptive_backtester.get_performance_summary()
        demo_report = demo_validator.generate_demo_report(adaptive_summary, adaptive_summary)
        print("✅ Demo validation report generated")
        
        print("📁 Reports saved in data/ directory")
        print("")
        
    except Exception as e:
        print(f"⚠️  Error generating reports: {e}")
        print("")

def open_dashboard_delayed():
    """Open dashboard after delay"""
    time.sleep(5)  # Wait for server to start
    try:
        webbrowser.open('http://127.0.0.1:8000')
        print("🌐 Dashboard opened in browser: http://127.0.0.1:8000")
    except Exception as e:
        print(f"⚠️  Could not auto-open browser: {e}")
        print("📊 Manually open: http://127.0.0.1:8000")

async def demo_learning_session():
    """Run demo learning session"""
    try:
        print("🚀 STARTING DEMO LEARNING SESSION...")
        print("⏰ Session started at:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("")
        
        # Show current progress
        show_learning_progress()
        
        # Start the bot with learning enabled
        print("🤖 Initializing V10 Scalping Bot with adaptive learning...")
        success = await main()
        
        return success
        
    except KeyboardInterrupt:
        print("\n🛑 Demo learning session interrupted by user")
        
        # Generate final reports
        print("\n📊 Generating final progress reports...")
        generate_progress_reports()
        
        return True
    except Exception as e:
        print(f"\n❌ Demo learning session error: {e}")
        return False

def main_demo_learning():
    """Main demo learning function"""
    print_demo_banner()
    
    # Safety checks first
    if not check_environment_safety():
        sys.exit(1)
    
    # Show current progress
    show_learning_progress()
    
    # Confirm demo mode
    print("🎯 DEMO LEARNING MODE CONFIRMED")
    print("   • No real money at risk")
    print("   • All trades are virtual")
    print("   • Learning from every trade")
    print("   • Building towards live trading readiness")
    print("")
    
    # Auto-open dashboard
    if '--no-browser' not in sys.argv:
        browser_thread = threading.Thread(target=open_dashboard_delayed, daemon=True)
        browser_thread.start()
    
    print("🔄 Starting adaptive learning session...")
    print("📊 Monitor progress at: http://127.0.0.1:8000")
    print("🛑 Press Ctrl+C to stop and generate reports")
    print("")
    
    # Run the demo learning session
    try:
        success = asyncio.run(demo_learning_session())
        
        if success:
            print("\n✅ Demo learning session completed successfully")
            
            # Generate final reports
            print("\n📊 Generating final comprehensive reports...")
            generate_progress_reports()
            
            # Check graduation status
            demo_validator = get_demo_validator()
            adaptive_backtester = get_adaptive_backtester()
            adaptive_summary = adaptive_backtester.get_performance_summary()
            graduation = demo_validator.check_graduation_criteria(adaptive_summary)
            
            print("\n🎓 FINAL GRADUATION ASSESSMENT:")
            print(f"   Overall Readiness: {graduation['overall_score']:.1%}")
            
            if graduation['ready_for_live']:
                print("🎉 CONGRATULATIONS! Ready for live trading!")
                print("📋 Next steps:")
                print("   1. Review all generated reports")
                print("   2. Start with minimum stakes on live account")
                print("   3. Monitor performance closely")
                print("   4. Be prepared to return to demo if needed")
            else:
                print("📚 Continue demo learning to improve readiness")
                print("📋 Recommendations:")
                for rec in graduation.get('recommendations', []):
                    print(f"   • {rec}")
            
            sys.exit(0)
        else:
            print("\n❌ Demo learning session failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n👋 Demo learning session ended by user")
        
        # Still generate reports
        generate_progress_reports()
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Fatal error in demo learning: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🎓 V10 Scalping Bot - Demo Learning Mode")
    print("=====================================")
    print("Safe demo trading with AI learning and graduation assessment")
    print("")
    
    # Check for help
    if '--help' in sys.argv or '-h' in sys.argv:
        print("USAGE:")
        print("  python run_demo_learning.py          # Start demo learning")
        print("  python run_demo_learning.py --no-browser  # Don't auto-open browser")
        print("")
        print("FEATURES:")
        print("  • Safe demo trading environment")
        print("  • Adaptive strategy learning")
        print("  • Real-time performance tracking")
        print("  • Web dashboard monitoring")
        print("  • Automatic graduation assessment")
        print("  • Comprehensive progress reports")
        sys.exit(0)
    
    main_demo_learning()