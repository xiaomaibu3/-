# Render Free 部署说明

## 适用范围

这个配置用于先跑通“手机和电脑访问同一个系统、看到同一份数据”的演示版。

Render Free 的 Web Service 文件系统是临时的，本项目当前仍使用 SQLite 和本地上传目录，所以免费部署不适合长期正式保存业务数据。重启、重新部署、闲置休眠后，录入数据和附件存在丢失风险。

## 部署步骤

1. 把 `project-management` 目录上传到一个 GitHub 仓库。
2. 登录 Render。
3. 选择 `New` -> `Blueprint`。
4. 连接 GitHub 仓库。
5. 如果仓库根目录不是 `project-management`，在 Render 的 Root Directory 中填 `project-management`。
6. Render 会读取 `render.yaml` 并创建免费 Web Service。
7. 部署完成后，打开 Render 分配的 `https://...onrender.com` 地址。

## 环境变量

`render.yaml` 已设置：

```text
MIMOCLAW_DATA_ROOT=/tmp/mimoclaw-data
```

建议在 Render 控制台额外添加：

```text
SECRET_KEY=<一串随机长文本>
```

`SECRET_KEY` 用于保持登录会话签名稳定。没有设置时系统也能运行，但每次重启后登录会话会失效。

## 访问方式

电脑端：

```text
https://你的服务名.onrender.com
```

手机端：

```text
https://你的服务名.onrender.com
```

手机和电脑访问同一个地址、登录同一个系统，就能看到同一份数据。

## 默认账号

```text
用户名：admin
密码：admin123
```

部署后请尽快进入用户管理，修改密码或创建新的管理员账号。

## 后续正式使用建议

正式长期使用时，建议升级为以下任一方案：

- 付费 Render 服务 + 持久磁盘
- 云服务器部署 + PostgreSQL/MySQL
- 手机 App 使用 WebView/Capacitor，访问同一个云端后端

