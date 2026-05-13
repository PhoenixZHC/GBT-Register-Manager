//! 机器人 Extension_Service（HTTP :5615）插件与 wheel 上传安装。
//! 由研发提供的逻辑整理；日志走 `crate::gbt_log`。

use std::{borrow::Cow, fs, path::Path, time::Duration};

use anyhow::{Context, Result, anyhow, bail, ensure};
use reqwest::{Response, multipart};
use serde::{Deserialize, Serialize, de::DeserializeOwned};
use serde_json::Value;
use url::Url;

#[derive(Debug, Clone, Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ExtensionInfo {
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub author: String,
    #[serde(rename = "type", default)]
    pub kind: String,
    #[serde(default)]
    pub script_lang: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub version: String,
    #[serde(default)]
    pub contact: String,
    #[serde(default)]
    pub copyright: String,
    #[serde(default)]
    pub license: String,
    #[serde(default)]
    pub entry: String,
    #[serde(default)]
    pub url: String,
}

#[derive(Debug, Clone)]
pub struct Extension {
    base_url: String,
    client: reqwest::Client,
}

const EXTENSION_SERVICE_NAME: &str = "Extension_Service";
const EXTENSION_SERVICE_PORT: u16 = 5615;
const DEFAULT_TIMEOUT_SECS: u64 = 30;
const LONG_TIMEOUT_SECS: u64 = 180;
const WHEEL_INSTALL_TIMEOUT_SECS: u64 = 300;
const RESPONSE_SUCCESS_STATUS_CODE: i32 = 1000;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AgilebotResponse<T> {
    status_code: i32,
    param: AgilebotResponseParam<T>,
}

#[derive(Debug, Deserialize)]
struct AgilebotResponseParam<T> {
    result: T,
}

impl Extension {
    /// 根据机器人主机地址创建插件安装客户端。
    pub fn new(robot_host: impl AsRef<str>) -> Result<Self> {
        let robot_host = robot_host.as_ref().trim().trim_end_matches('/');
        ensure!(!robot_host.is_empty(), "Extension_Service 地址不能为空");

        let base_url = build_http_base_url(robot_host, EXTENSION_SERVICE_PORT)?;
        let client = build_http_client_for_host(robot_host, Duration::from_secs(DEFAULT_TIMEOUT_SECS))?;
        crate::gbt_log(&format!("Extension::new base_url={base_url}"));
        Ok(Self { base_url, client })
    }

    /// 上传并安装插件包，对应 `POST /extension`。
    pub async fn install_extension(
        &self,
        path: &Path,
        display_name: &str,
    ) -> Result<ExtensionInfo> {
        crate::gbt_log(&format!(
            "install_extension base_url={} path=/extension file={}",
            self.base_url,
            path.display()
        ));
        let response = post_file(
            &self.base_url,
            &self.client,
            "/extension",
            path,
            display_name,
            Duration::from_secs(LONG_TIMEOUT_SECS),
        )
        .await?;

        let result = parse_agilebot_response(response, EXTENSION_SERVICE_NAME, "/extension").await;
        crate::gbt_log(&format!("install_extension result_ok={}", result.is_ok()));
        result
    }

    /// 上传并安装 Python wheel，对应 `POST /env/wheel`。
    /// 成功仅依据 `statusCode == 1000`，不强制解析 `result` 形态（避免服务端返回非 bool）。
    pub async fn install_wheel(&self, path: &Path, display_name: &str) -> Result<()> {
        crate::gbt_log(&format!(
            "install_wheel base_url={} path=/env/wheel file={}",
            self.base_url,
            path.display()
        ));
        let response = post_file(
            &self.base_url,
            &self.client,
            "/env/wheel",
            path,
            display_name,
            Duration::from_secs(WHEEL_INSTALL_TIMEOUT_SECS),
        )
        .await?;

        parse_agilebot_response_ok(response, EXTENSION_SERVICE_NAME, "/env/wheel").await?;
        crate::gbt_log("install_wheel ok");
        Ok(())
    }
}

async fn post_file(
    base_url: &str,
    client: &reqwest::Client,
    path: &str,
    file_path: &Path,
    display_name: &str,
    timeout: Duration,
) -> Result<Response> {
    let bytes =
        fs::read(file_path).with_context(|| format!("读取附件失败: {}", file_path.display()))?;
    let form = multipart::Form::new().part(
        "file",
        multipart::Part::bytes(bytes).file_name(display_name.to_string()),
    );
    let url = join_http_url(base_url, path);
    crate::gbt_log(&format!(
        "post_file url={url} file_path={} display_name={} timeout_secs={}",
        file_path.display(),
        display_name,
        timeout.as_secs()
    ));

    client
        .post(url)
        .multipart(form)
        .timeout(timeout)
        .send()
        .await
        .with_context(|| format!("调用 {EXTENSION_SERVICE_NAME} 失败: {path}"))
}

fn build_http_base_url(host: &str, port: u16) -> Result<String> {
    let trimmed = host.trim().trim_end_matches('/');
    ensure!(!trimmed.is_empty(), "HTTP 地址不能为空");

    let candidate = if trimmed.contains("://") {
        Cow::Borrowed(trimmed)
    } else {
        Cow::Owned(format!("http://{trimmed}"))
    };
    let mut url =
        Url::parse(candidate.as_ref()).with_context(|| format!("解析 HTTP 地址失败: {trimmed}"))?;
    url.set_port(Some(port))
        .map_err(|()| anyhow!("设置 HTTP 端口失败: {port}"))?;
    Ok(normalize_http_url(&url))
}

fn build_http_client_for_host(host: &str, timeout: Duration) -> Result<reqwest::Client> {
    let _ = host;
    reqwest::Client::builder()
        .timeout(timeout)
        .no_proxy()
        .build()
        .map_err(|e| anyhow!("创建 HTTP 客户端失败：{e}"))
}

fn join_http_url(base_url: &str, path: &str) -> String {
    Url::parse(base_url)
        .ok()
        .and_then(|mut url| {
            let mut base_path = url.path().to_string();
            if !base_path.ends_with('/') {
                base_path.push('/');
                url.set_path(&base_path);
            }

            let relative_path = path.strip_prefix('/').unwrap_or(path);
            url.join(relative_path).ok().map(Into::into)
        })
        .unwrap_or_else(|| format_http_url_fallback(base_url, path))
}

async fn parse_agilebot_response<Res>(
    response: Response,
    service_name: &str,
    endpoint: &str,
) -> Result<Res>
where
    Res: DeserializeOwned,
{
    let http_status = response.status();
    let body = response
        .text()
        .await
        .with_context(|| format!("读取 {service_name} 响应失败: {endpoint}"))?;
    crate::gbt_log(&format!(
        "parse_agilebot_response service={service_name} endpoint={endpoint} http_status={http_status} body_len={}",
        body.len()
    ));

    ensure!(
        http_status.is_success(),
        "{service_name} 返回 HTTP {http_status}: {body}"
    );

    let envelope: AgilebotResponse<Value> = serde_json::from_str(&body)
        .with_context(|| format!("解析 {service_name} 响应失败: {endpoint}"))?;

    if envelope.status_code != RESPONSE_SUCCESS_STATUS_CODE {
        bail!("{}", extract_error_message(envelope.param.result));
    }

    serde_json::from_value(envelope.param.result)
        .with_context(|| format!("解析 {endpoint} 结果失败"))
}

/// wheel 等接口成功时 `result` 可能为 bool、对象或 null，仅校验业务状态码。
async fn parse_agilebot_response_ok(
    response: Response,
    service_name: &str,
    endpoint: &str,
) -> Result<()> {
    let http_status = response.status();
    let body = response
        .text()
        .await
        .with_context(|| format!("读取 {service_name} 响应失败: {endpoint}"))?;
    crate::gbt_log(&format!(
        "parse_agilebot_response_ok service={service_name} endpoint={endpoint} http_status={http_status} body_len={}",
        body.len()
    ));

    ensure!(
        http_status.is_success(),
        "{service_name} 返回 HTTP {http_status}: {body}"
    );

    let envelope: AgilebotResponse<Value> = serde_json::from_str(&body)
        .with_context(|| format!("解析 {service_name} 响应失败: {endpoint}"))?;

    if envelope.status_code != RESPONSE_SUCCESS_STATUS_CODE {
        bail!("{}", extract_error_message(envelope.param.result));
    }
    Ok(())
}

fn extract_error_message(value: Value) -> String {
    match value {
        Value::String(message) => message,
        Value::Object(mut object) => {
            if let Some(Value::String(message)) = object.remove("msg") {
                message
            } else if let Some(Value::String(message)) = object.remove("message") {
                message
            } else if let Some(Value::String(message)) = object.remove("error") {
                message
            } else {
                Value::Object(object).to_string()
            }
        }
        other => other.to_string(),
    }
}

fn normalize_http_url(url: &Url) -> String {
    url.as_str().trim_end_matches('/').to_string()
}

fn format_http_url_fallback(base_url: &str, path: &str) -> String {
    let base_url = base_url.trim().trim_end_matches('/');
    let normalized_path = match path.chars().next() {
        Some('?' | '#') => Cow::Borrowed(path),
        _ => Cow::Owned(format!("/{}", path.trim_start_matches('/'))),
    };
    format!("{base_url}{normalized_path}")
}
