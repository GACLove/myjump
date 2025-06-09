# MyJump - SSH 自动登录工具

MyJump 是一个命令行工具，用于简化 SSH 登录过程，特别是当您需要处理 OTP (一次性密码) 和密码时。它支持配置管理，可以将常用的服务器、用户名、OTP Secret 和密码保存到本地配置文件中。

## 安装

```bash
pip install git+https://github.com/GACLove/myjump.git
```

也可以从 GitHub 克隆源代码并进行安装。

1. **克隆仓库:**

    ```bash
    git clone https://github.com/gaopeng/myjump.git
    cd myjump
    ```

    (请将 `https://github.com/gaopeng/myjump.git` 替换为您的实际仓库地址)

2. **通过源码安装 (推荐开发模式):**
    在项目根目录下运行 (包含 `pyproject.toml` 的目录):

    ```bash
    pip install -e .
    ```

    这将安装 `myjump` 包及其所有依赖，并创建一个名为 `myjump` 的可执行命令。

### 依赖

本工具依赖以下 Python 库：

- `pyotp`
- `pexpect`

它们会在 `pip install` 时自动安装。

## 配置

MyJump 会在您的用户主目录下创建配置目录 `~/.my-jump/`，并在其中生成 `config.json` 文件来存储配置。

您可以使用 `myjump config` 命令来管理配置。

### 设置配置

使用 `set` 命令来设置配置项。

- **设置默认 Jump Server 地址:**

  ```bash
  myjump config set -k jump_server -v jump.example.com
  ```

- **设置默认用户名:**

  ```bash
  myjump config set -k username -v your_username
  ```

- **设置默认 OTP Secret Key:**

  ```bash
  myjump config set -k otp_secret -v YOUR_OTP_SECRET_KEY
  ```

- **设置默认密码 (不推荐直接在命令行中输入):**

  ```bash
  myjump config set -k password -v your_password
  ```

  当您设置密码时，工具会提示您进行确认，并将其加密存储。

- **设置特定配置 Profiles:**
  您可以为不同的服务器或用户创建独立的配置 profile。

  ```bash
  myjump config set -P my_profile -k jump_server -v another_jump.example.com
  myjump config set -P my_profile -k username -v another_user
  myjump config set -P my_profile -k otp_secret -v ANOTHER_OTP_SECRET_KEY
  ```

### 查看配置

- **查看所有配置:**

  ```bash
  myjump config get
  ```

- **查看特定配置项:**

  ```bash
  myjump config get -k username
  myjump config get -P my_profile -k jump_server
  ```

### 列出配置 Profiles

- **列出所有已保存的 profiles:**

  ```bash
  myjump config list
  ```

### 删除配置 Profile

- **删除一个配置 profile:**

  ```bash
  myjump config delete -P my_profile
  ```

  删除前会要求确认。

## 使用 (登录)

配置完成后，您可以使用 `myjump login` 命令进行 SSH 登录。

- **使用默认配置登录:**
  如果已设置所有必要的默认配置 (`jump_server`, `username`, `otp_secret`)，直接运行:

  ```bash
  myjump login
  ```

  如果密码未保存，它将提示您输入密码。

- **使用特定 profile 登录:**

  ```bash
  myjump login -P my_profile
  ```

- **命令行指定参数登录 (会覆盖配置文件中的设置):**

  ```bash
  myjump login -j jump.example.com -u your_username -s YOUR_OTP_SECRET_KEY -p your_password
  ```

  **注意:** 在命令行中直接指定密码 (`-p`) 是不安全的，建议使用配置文件管理密码。

- **显示详细交互过程:**
  在登录时添加 `-v` 或 `--verbose` 参数可以显示 SSH 交互的详细日志。

  ```bash
  myjump login -v
  ```

希望这份 README 文档能够帮助您更好地使用 MyJump 工具！

## FAQ

1. 安装遇到提示是 `Successfully uninstalled UNKNOWN-0.0.0` 的错误，可以尝试使用 `pip install --upgrade pip setuptools wheel build` 升级 setuptools 解决。  
