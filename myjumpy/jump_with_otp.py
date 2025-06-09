#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SSH自动登录脚本 - 支持配置文件
依赖: pip install pyotp pexpect
"""

import argparse
import base64
import getpass
import json
import logging
import os
import sys
from pathlib import Path

import pexpect
import pyotp


class ConfigManager:
    """配置文件管理器"""

    def __init__(self):
        self.config_dir = Path.home() / ".my-jump"
        self.config_file = self.config_dir / "config.json"
        self.ensure_config_dir()

    def ensure_config_dir(self):
        """确保配置目录存在"""
        if not self.config_dir.exists():
            self.config_dir.mkdir(mode=0o700, parents=True)
            logging.info(f"[+] 创建配置目录: {self.config_dir}")

    def encode_password(self, password: str) -> str:
        """使用base64编码密码"""
        return base64.b64encode(password.encode("utf-8")).decode("utf-8")

    def decode_password(self, encoded_password: str) -> str:
        """解码base64密码"""
        try:
            return base64.b64decode(encoded_password.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logging.error(f"[-] 解码密码失败: {e}")
            return ""

    def load_config(self) -> dict:
        """加载配置文件"""
        default_config = {
            "jump_server": "jump.example.com",
            "username": "",
            "otp_secret": "",
            "password": "",  # base64编码的密码
            "profiles": {},  # 支持多个配置文件
        }

        if not self.config_file.exists():
            self.save_config(default_config)
            logging.info(f"[+] 创建默认配置文件: {self.config_file}")
            return default_config

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            # 合并默认配置，确保所有必要的键都存在
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
        except Exception as e:
            logging.error(f"[-] 加载配置文件失败: {e}")
            return default_config

    def save_config(self, config: dict):
        """保存配置文件"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            # 设置文件权限为只有所有者可读写
            os.chmod(self.config_file, 0o600)
            logging.info(f"[+] 配置已保存到: {self.config_file}")
        except Exception as e:
            logging.error(f"[-] 保存配置文件失败: {e}")

    def set_config(self, key: str, value: str, profile: str = None):
        """设置配置项"""
        config = self.load_config()

        if profile:
            # 设置特定profile的配置
            if "profiles" not in config:
                config["profiles"] = {}
            if profile not in config["profiles"]:
                config["profiles"][profile] = {}

            if key == "password":
                config["profiles"][profile][key] = self.encode_password(value)
            else:
                config["profiles"][profile][key] = value
        else:
            # 设置默认配置
            if key == "password":
                config[key] = self.encode_password(value)
            else:
                config[key] = value

        self.save_config(config)
        logging.info(f"[+] 设置配置项 {key} = {'*' * len(value) if key == 'password' else value}")

    def get_config(self, key: str, profile: str = None) -> str:
        """获取配置项"""
        config = self.load_config()

        if profile and "profiles" in config and profile in config["profiles"]:
            # 从特定profile获取配置
            profile_config = config["profiles"][profile]
            if key in profile_config:
                value = profile_config[key]
                if key == "password":
                    return self.decode_password(value)
                return value

        # 从默认配置获取
        if key in config:
            value = config[key]
            if key == "password":
                return self.decode_password(value)
            return value

        return ""

    def list_profiles(self) -> list:
        """列出所有配置文件"""
        config = self.load_config()
        return list(config.get("profiles", {}).keys())

    def delete_profile(self, profile: str):
        """删除配置文件"""
        config = self.load_config()
        if "profiles" in config and profile in config["profiles"]:
            del config["profiles"][profile]
            self.save_config(config)
            logging.info(f"[+] 删除配置文件: {profile}")
        else:
            logging.error(f"[-] 配置文件不存在: {profile}")


def get_otp_code(secret_key):
    """根据给定的 secret key 生成当前的 OTP 验证码"""
    try:
        totp = pyotp.TOTP(secret_key)
        return totp.now()
    except Exception as e:
        logging.error(f"[-] 生成 OTP 失败: {e}")
        logging.error("[-] 请检查你的 OTP Secret Key 是否正确。")
        sys.exit(1)


def ssh_login(hostname, username, password, otp_code, verbose=False):
    """使用 pexpect 自动处理 SSH 登录交互"""
    child = None
    try:
        # 构建 SSH 命令
        ssh_command = f"ssh -o StrictHostKeyChecking=no {username}@{hostname}"
        logging.info(f"[+] 正在尝试连接到: {ssh_command}")

        # 启动 ssh 进程
        child = pexpect.spawn(ssh_command, encoding="utf-8", timeout=30)

        # 可选：如果需要查看详细交互过程
        if verbose:
            child.logfile_read = sys.stdout

        # 匹配常见的 shell 提示符，表示登录成功
        shell_prompt = r"[\$#>]\s*$"

        # 登录交互序列
        patterns = [
            r"[Pp]assword\s*:",  # 0: 密码提示
            r"(\[OTP Code\]|[Vv]erification [Cc]ode|[Oo]TP [Cc]ode|\[MFA auth\])\s*:",  # 1: OTP/验证码提示
            r"continue connecting \(yes/no.*?\)\?",  # 2: 首次连接的key确认
            shell_prompt,  # 3: 登录成功后的shell提示符
            r"Permission denied",  # 4: 权限被拒绝
            r"Authentication failed",  # 5: 认证失败
            pexpect.EOF,  # 6: 连接被关闭
            pexpect.TIMEOUT,  # 7: 超时
        ]

        login_attempts = 0
        max_attempts = 3

        while login_attempts < max_attempts:
            try:
                logging.info(f"[+] 等待服务器响应... (尝试 {login_attempts + 1}/{max_attempts})")
                index = child.expect(patterns, timeout=30)

                if index == 0:  # 匹配到 Password
                    logging.info("[+] 检测到密码提示，正在输入密码...")
                    child.sendline(password)
                elif index == 1:  # 匹配到 Verification Code
                    logging.info(f"[+] 检测到验证码提示，正在输入 OTP: {otp_code}")
                    child.sendline(otp_code)
                elif index == 2:  # 首次连接
                    logging.info("[+] 接受新的 SSH 主机密钥...")
                    child.sendline("yes")
                elif index == 3:  # 匹配到 Shell 提示符，登录成功
                    print("\n" + "=" * 50)
                    print("[+] 登录成功！已进入交互模式。")
                    print("按 Ctrl+] 退出交互模式")
                    print("=" * 50 + "\n")
                    # 将控制权交给用户
                    child.interact()
                    return  # 成功登录，退出函数
                elif index in [4, 5]:  # 权限被拒绝或认证失败
                    logging.error(f"[-] 认证失败 (尝试 {login_attempts + 1}/{max_attempts})")
                    if login_attempts < max_attempts - 1:
                        logging.info("[+] 重新生成 OTP 验证码...")
                        # 重新生成OTP，因为可能时间过期了
                        config_manager = ConfigManager()
                        secret_key = config_manager.get_config("otp_secret")
                        otp_code = get_otp_code(secret_key)
                        login_attempts += 1
                        continue
                    else:
                        logging.error("[-] 达到最大重试次数，登录失败")
                        break
                elif index == 6:  # EOF，连接已关闭
                    logging.error("[-] 连接被服务器关闭")
                    if child.before:
                        logging.error(f"[-] 服务器返回信息: {child.before}")
                    break
                elif index == 7:  # 超时
                    logging.error("[-] 等待服务器响应超时")
                    if child.before:
                        logging.error(f"[-] 超时前的输出: {child.before}")
                    break

            except pexpect.TIMEOUT:
                logging.error(f"[-] 操作超时 (尝试 {login_attempts + 1}/{max_attempts})")
                login_attempts += 1
                if login_attempts >= max_attempts:
                    logging.error("[-] 达到最大重试次数")
                    break
            except pexpect.EOF:
                logging.error("[-] 连接意外关闭")
                break

    except pexpect.exceptions.ExceptionPexpect as e:
        logging.error(f"[-] Pexpect 发生错误: {e}")
    except Exception as e:
        logging.error(f"[-] 发生未知错误: {e}")
        logging.exception("详细错误信息:")
    finally:
        # 确保子进程被关闭
        if child and child.isalive():
            child.close()
        logging.info("[+] 连接已关闭。")


def configure_command(args):
    """配置命令处理"""
    config_manager = ConfigManager()

    if args.action == "set":
        if not args.key or not args.value:
            logging.error("[-] 设置配置需要指定 key 和 value")
            return

        if args.key == "password":
            # 确认密码设置
            confirm = input(f"确认要将密码设置为 {'*' * len(args.value)} ? (y/N): ")
            if confirm.lower() != "y":
                logging.info("操作已取消")
                return

        config_manager.set_config(args.key, args.value, args.profile)

    elif args.action == "get":
        if not args.key:
            # 显示所有配置
            config = config_manager.load_config()
            print("\n当前配置:")
            print("-" * 40)
            for key, value in config.items():
                if key == "password":
                    print(f"{key}: {'*' * len(value) if value else '(未设置)'}")
                elif key == "profiles":
                    if value:
                        print(f"{key}: {list(value.keys())}")
                    else:
                        print(f"{key}: []")
                else:
                    print(f"{key}: {value}")
        else:
            value = config_manager.get_config(args.key, args.profile)
            if args.key == "password":
                print(f"{args.key}: {'*' * len(value) if value else '(未设置)'}")
            else:
                print(f"{args.key}: {value}")

    elif args.action == "list":
        profiles = config_manager.list_profiles()
        if profiles:
            print(f"可用的配置文件: {', '.join(profiles)}")
        else:
            print("没有配置文件")

    elif args.action == "delete":
        if not args.profile:
            logging.error("[-] 删除配置文件需要指定 --profile")
            return
        confirm = input(f"确认要删除配置文件 '{args.profile}' ? (y/N): ")
        if confirm.lower() == "y":
            config_manager.delete_profile(args.profile)
        else:
            logging.info("操作已取消")


def login_command(args):
    """登录命令处理"""
    config_manager = ConfigManager()

    # 从配置文件或命令行参数获取值
    hostname = args.jump or config_manager.get_config("jump_server", args.profile)
    username = args.username or config_manager.get_config("username", args.profile)
    secret_key = args.secret or config_manager.get_config("otp_secret", args.profile)

    # 密码处理
    password = None
    if args.password:
        password = args.password
        logging.warning("[!] 警告: 在命令行中传递密码不安全")
    else:
        # 尝试从配置文件获取密码
        saved_password = config_manager.get_config("password", args.profile)
        if saved_password:
            use_saved = input(f"使用已保存的密码? (Y/n): ")
            if use_saved.lower() != "n":
                password = saved_password

        if not password:
            try:
                password = getpass.getpass(prompt=f"请输入用户 {username} 的密码: ")
                # 询问是否保存密码
                save_password = input("是否保存密码到配置文件? (y/N): ")
                if save_password.lower() == "y":
                    config_manager.set_config("password", password, args.profile)
            except KeyboardInterrupt:
                logging.info("\n操作已取消。")
                sys.exit(0)

    if not password:
        logging.error("[-] 密码不能为空")
        sys.exit(1)

    # 验证必要参数
    if not all([hostname, username, secret_key]):
        logging.error("[-] 缺少必要的连接参数")
        logging.error(f"    hostname: {hostname or '(未设置)'}")
        logging.error(f"    username: {username or '(未设置)'}")
        logging.error(f"    otp_secret: {secret_key[:4] + '***' if secret_key else '(未设置)'}")
        logging.error("请使用 'python a.py config set' 设置这些参数")
        sys.exit(1)

    # 生成 OTP
    logging.info(f"[+] 连接到: {username}@{hostname}")
    logging.info(f"[+] 使用 Secret Key: {secret_key[:4]}***{secret_key[-4:]} (部分隐藏)")
    otp_code = get_otp_code(secret_key)
    logging.info(f"[+] 生成的 OTP 验证码: {otp_code}")

    # 执行登录
    ssh_login(hostname, username, password, otp_code, args.verbose)


def main():
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    parser = argparse.ArgumentParser(
        description="SSH自动登录工具 - 支持配置文件管理",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # 登录命令 (默认)
    login_parser = subparsers.add_parser("login", help="登录到jump server")
    login_parser.add_argument("-j", "--jump", help="跳板机地址")
    login_parser.add_argument("-u", "--username", help="登录用户名")
    login_parser.add_argument("-s", "--secret", help="OTP Secret Key")
    login_parser.add_argument("-p", "--password", help="登录密码 (不推荐)")
    login_parser.add_argument("-P", "--profile", help="使用指定的配置文件")
    login_parser.add_argument("-v", "--verbose", action="store_true", help="显示详细交互过程")

    # 配置命令
    config_parser = subparsers.add_parser("config", help="配置文件管理")
    config_parser.add_argument("action", choices=["set", "get", "list", "delete"], help="配置操作")
    config_parser.add_argument("-k", "--key", help="配置项名称 (jump_server, username, otp_secret, password)")
    config_parser.add_argument("-v", "--value", help="配置项值")
    config_parser.add_argument("-P", "--profile", help="配置文件名")

    # 如果没有参数，默认执行登录
    if len(sys.argv) == 1:
        args = parser.parse_args(["login"])
    else:
        args = parser.parse_args()

    if args.command == "config":
        configure_command(args)
    else:
        login_command(args)


if __name__ == "__main__":
    """
    python jump.py login -j jump.example.com -u gaopeng1 -s xxxxxx
    python jump.py config set -k jump_server -v jump.example.com
    python jump.py config set -k username -v gaopeng1
    python jump.py config set -k otp_secret -v xxxxxx
    python jump.py config set -k password -v xxxxxx
    python jump.py config list
    python jump.py config delete -p gaopeng1
    python jump.py config get -k jump_server
    python jump.py config get -k username
    python jump.py config get -k otp_secret
    python jump.py config get -k password
    """
    main()
