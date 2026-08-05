package com.xinggui.app;

import android.annotation.TargetApi;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.KeyguardManager;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.hardware.biometrics.BiometricPrompt;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.SslErrorHandler;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public class MainActivity extends Activity {
    private static final String WEB_APP_URL = "http://154.12.85.176/";
    private static final String PREFS_NAME = "xinggui_secure_login";
    private static final String KEY_ALIAS = "xinggui_local_login_key";
    private static final String PREF_USERNAME = "username";
    private static final String PREF_CIPHER = "cipher";
    private static final String PREF_IV = "iv";
    private static final int REQUEST_DEVICE_CREDENTIAL = 6001;

    private WebView webView;
    private Runnable pendingAuthenticatedAction;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        webView.setLayoutParams(new ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        }

        webView.addJavascriptInterface(new NativeBridge(), "XingguiNative");
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.cancel();
            }
        });
        webView.loadUrl(WEB_APP_URL);
        setContentView(webView);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        super.onBackPressed();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_DEVICE_CREDENTIAL) {
            Runnable action = pendingAuthenticatedAction;
            pendingAuthenticatedAction = null;
            if (resultCode == RESULT_OK && action != null) {
                action.run();
            } else {
                showNativeMessage("验证已取消");
            }
        }
    }

    public class NativeBridge {
        @JavascriptInterface
        public boolean hasSavedLogin() {
            return getPrefs().contains(PREF_CIPHER) && getPrefs().contains(PREF_IV);
        }

        @JavascriptInterface
        public void enableCredentialLogin(final String username, final String password) {
            if (username == null || username.trim().isEmpty() || password == null || password.isEmpty()) {
                return;
            }
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    new AlertDialog.Builder(MainActivity.this)
                        .setTitle("启用指纹登录")
                        .setMessage("以后可通过系统指纹或锁屏验证自动登录星轨。登录信息会加密保存在本机。")
                        .setPositiveButton("启用", new DialogInterface.OnClickListener() {
                            @Override
                            public void onClick(DialogInterface dialog, int which) {
                                authenticate("启用指纹登录", new Runnable() {
                                    @Override
                                    public void run() {
                                        saveEncryptedCredentials(username, password);
                                    }
                                });
                            }
                        })
                        .setNegativeButton("暂不启用", null)
                        .show();
                }
            });
        }

        @JavascriptInterface
        public void requestFingerprintLogin() {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    if (!hasSavedLogin()) {
                        showNativeMessage("请先使用账号密码登录并启用指纹登录");
                        return;
                    }
                    authenticate("指纹登录", new Runnable() {
                        @Override
                        public void run() {
                            injectSavedCredentials();
                        }
                    });
                }
            });
        }

        @JavascriptInterface
        public void clearSavedLogin() {
            getPrefs().edit().clear().apply();
            showNativeMessage("已清除本机指纹登录");
        }
    }

    private SharedPreferences getPrefs() {
        return getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
    }

    private void authenticate(String title, Runnable action) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            authenticateWithBiometricPrompt(title, action);
            return;
        }
        authenticateWithDeviceCredential(title, action);
    }

    @TargetApi(Build.VERSION_CODES.P)
    private void authenticateWithBiometricPrompt(String title, Runnable action) {
        BiometricPrompt prompt = new BiometricPrompt.Builder(this)
            .setTitle(title)
            .setSubtitle("使用系统指纹验证身份")
            .setNegativeButton("取消", getMainExecutor(), new DialogInterface.OnClickListener() {
                @Override
                public void onClick(DialogInterface dialog, int which) {
                    showNativeMessage("验证已取消");
                }
            })
            .build();

        prompt.authenticate(new CancellationSignal(), getMainExecutor(), new BiometricPrompt.AuthenticationCallback() {
            @Override
            public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result) {
                action.run();
            }

            @Override
            public void onAuthenticationError(int errorCode, CharSequence errString) {
                if (errorCode != BiometricPrompt.BIOMETRIC_ERROR_USER_CANCELED) {
                    authenticateWithDeviceCredential(title, action);
                }
            }

            @Override
            public void onAuthenticationFailed() {
                showNativeMessage("指纹验证失败，请重试");
            }
        });
    }

    private void authenticateWithDeviceCredential(String title, Runnable action) {
        KeyguardManager keyguard = (KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
        if (keyguard == null || !keyguard.isKeyguardSecure()) {
            showNativeMessage("请先在手机系统中设置锁屏密码或指纹");
            return;
        }
        pendingAuthenticatedAction = action;
        Intent intent = keyguard.createConfirmDeviceCredentialIntent(title, "验证后继续使用星轨");
        if (intent == null) {
            showNativeMessage("当前设备不支持系统验证");
            return;
        }
        startActivityForResult(intent, REQUEST_DEVICE_CREDENTIAL);
    }

    private SecretKey getOrCreateSecretKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        if (keyStore.containsAlias(KEY_ALIAS)) {
            return (SecretKey) keyStore.getKey(KEY_ALIAS, null);
        }

        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        KeyGenParameterSpec spec = new KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setUserAuthenticationRequired(true)
            .setUserAuthenticationValidityDurationSeconds(30)
            .build();
        generator.init(spec);
        return generator.generateKey();
    }

    private void saveEncryptedCredentials(String username, String password) {
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, getOrCreateSecretKey());
            byte[] encrypted = cipher.doFinal((username + "\n" + password).getBytes(StandardCharsets.UTF_8));

            getPrefs().edit()
                .putString(PREF_USERNAME, username)
                .putString(PREF_CIPHER, Base64.encodeToString(encrypted, Base64.NO_WRAP))
                .putString(PREF_IV, Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .apply();
            showNativeMessage("指纹登录已启用");
        } catch (Exception ex) {
            showNativeMessage("启用失败，请确认手机已设置指纹或锁屏");
        }
    }

    private void injectSavedCredentials() {
        try {
            SharedPreferences prefs = getPrefs();
            byte[] encrypted = Base64.decode(prefs.getString(PREF_CIPHER, ""), Base64.NO_WRAP);
            byte[] iv = Base64.decode(prefs.getString(PREF_IV, ""), Base64.NO_WRAP);

            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateSecretKey(), new GCMParameterSpec(128, iv));
            String[] parts = new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8).split("\n", 2);
            if (parts.length != 2) {
                showNativeMessage("本机登录信息异常，请重新启用指纹登录");
                return;
            }

            String script = "window.dispatchEvent(new CustomEvent('xinggui:credentials',{detail:{username:"
                + JSONObject.quote(parts[0]) + ",password:" + JSONObject.quote(parts[1]) + "}}));";
            webView.evaluateJavascript(script, null);
        } catch (Exception ex) {
            showNativeMessage("验证失败或登录信息已失效，请重新输入密码登录");
        }
    }

    private void showNativeMessage(final String message) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                Toast.makeText(MainActivity.this, message, Toast.LENGTH_SHORT).show();
            }
        });
    }
}
