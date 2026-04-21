#!python
"""
Copyright © 2016 Agilebot Robotics Ltd. All rights reserved.
Instruction: 自然语言基础控制示例 / Natural Language Basic Control Example
"""

from Agilebot import Arm, StatusCodeEnum

# [ZH] 初始化捷勃特机器人
# [EN] Initialize the Agilebot robot
arm = Arm()
# [ZH] 连接捷勃特机器人
# [EN] Connect to the Agilebot robot
ret = arm.connect("10.27.1.254")

# [ZH] 检查是否连接成功
# [EN] Check if connection is successful
if ret == StatusCodeEnum.OK:
    print("机器人连接成功 / Robot connected successfully")
else:
    print(f"机器人连接失败，错误代码 / Robot connection failed, error code: {ret.errmsg}")
    arm.disconnect()
    exit(1)


# [ZH] 示例：使用自然语言获取控制器版本信息
# [EN] Example: Use natural language to get controller version information
result, ret = arm.nlu.execute("获取控制器版本信息")

if ret == StatusCodeEnum.OK:
    print("自然语言指令执行成功 / Natural language command executed successfully")

    if result.needs_approval:
        print("\n" + "=" * 50)
        print("警告：需要用户确认 / Warning: User Approval Required")
        print("=" * 50)

        result.print_code()
        print("\n请确认是否执行此代码 / Please confirm if you want to execute this code:")
        user_input = input("\n(yes/no): ").strip().lower()
        if user_input not in ["yes", "y"]:
            print("用户拒绝执行代码 / User rejected code execution")
            arm.disconnect()
            exit(1)
        else:
            result.approve()
    exec_result, ret = result.execute_code()
    if ret == StatusCodeEnum.OK:
        print(f"执行结果 / Execution result: {exec_result}")
else:
    print(f"自然语言指令执行失败 / Natural language command failed: {ret.errmsg}")

# [ZH] 断开捷勃特机器人连接
# [EN] Disconnect from Agilebot robot
arm.disconnect()
print("\n机器人断开连接成功 / Robot disconnected successfully")
