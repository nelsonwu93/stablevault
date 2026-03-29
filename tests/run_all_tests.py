"""
QA测试运行器 — 运行所有测试用例
用法: python3 tests/run_all_tests.py
"""

import unittest
import sys
import os

# 确保项目根目录在path中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=os.path.dirname(__file__),
        pattern="test_*.py",
    )

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出汇总
    print("\n" + "=" * 70)
    print(f"总计: {result.testsRun} 个测试")
    print(f"通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print("=" * 70)

    if result.failures:
        print("\n❌ 失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split(chr(10))[-2]}")

    if result.errors:
        print("\n💥 出错的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split(chr(10))[-2]}")

    if result.wasSuccessful():
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 存在失败或错误，需要修复")

    sys.exit(0 if result.wasSuccessful() else 1)
