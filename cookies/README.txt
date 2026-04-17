将 Netscape 格式的 cookies.txt 放在此目录。

## 推荐导出工具

- **EditThisCookie**（Chrome/Edge 扩展）→ Export → 选 Netscape 格式 ✅ 推荐
- **Cookie-Editor**（多浏览器）→ Export → Format: Netscape
- Chrome DevTools **不推荐**——默认只导出 `__Secure-*` 系列 cookie，
  缺少 YouTube 认证必需的 HSID/SSID/APISID/SAPISID，会导致
  "Sign in to confirm you're not a bot" 错误。

## 必须包含的 Cookie 字段

一个有效的 YouTube cookie 文件**必须包含**以下字段：

| 字段 | 说明 |
|------|------|
| `HSID` | 用户身份 ID（必须有） |
| `SSID` | Session ID（必须有） |
| `APISID` | Google API 安全 cookie（必须有） |
| `SAPISID` | Google API 安全 cookie（必须有） |
| `LOGIN_INFO` | YouTube 登录信息 |
| `PREF` | 用户偏好设置 |

## 格式示例

```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	1807969509	HSID	A123456789
.youtube.com	TRUE	/	TRUE	1807969509	SSID	Abcdefghijk
.youtube.com	TRUE	/	TRUE	1810811627	APISID	xxxxxxxxxx/xxxxxxxxxx
.youtube.com	TRUE	/	TRUE	1810811627	SAPISID	xxxxxxxxxx/xxxxxxxxxx
.youtube.com	TRUE	/	FALSE	0	PREF	f4=4000000&f6=40000000&tz=UTC
.youtube.com	TRUE	/	TRUE	0	YSC	OeehyhJ0Blc
.youtube.com	TRUE	/	TRUE	1791987102	VISITOR_INFO1_LIVE	rtDUsPIxrX8
```

⚠️ 注意：必须是 **Netscape 格式**，不是 JSON！

此文件已配置 .gitignore，不会被提交到版本库。
