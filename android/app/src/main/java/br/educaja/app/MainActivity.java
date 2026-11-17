package br.educaja.app;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

/**
 * Educa Já: abre o site publicado numa tela própria, sem barra de endereço.
 * Os dados e o visual vêm sempre do site, então atualizações do site chegam sem gerar APK novo.
 * Para trocar o endereço (por exemplo, um domínio próprio), mude SITE, HOST e CAMINHO.
 */
public class MainActivity extends Activity {

    static final String SITE = "https://hubja.com.br/educa-ja/";
    static final String HOST = "hubja.com.br";
    static final String HOST_ANTIGO = "correaglicelio.github.io"; // endereço antigo (redireciona para o novo)
    static final String CAMINHO = "/educa-ja";
    static final int PEDIDO_LOCAL = 1;

    private WebView web;
    private GeolocationPermissions.Callback geoCallback;
    private String geoOrigem;

    @Override
    protected void onCreate(Bundle salvo) {
        super.onCreate(salvo);
        FrameLayout raiz = new FrameLayout(this);
        raiz.setBackgroundColor(Color.parseColor("#1C2A78"));
        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#F4F6F8"));
        raiz.addView(web, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(raiz);

        // Android 15+ desenha o app atrás das barras do sistema: afastamos o conteúdo delas (e do teclado).
        raiz.setOnApplyWindowInsetsListener((v, ins) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets i = ins.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
                v.setPadding(i.left, i.top, i.right, i.bottom);
            } else {
                v.setPadding(ins.getSystemWindowInsetLeft(), ins.getSystemWindowInsetTop(),
                        ins.getSystemWindowInsetRight(), ins.getSystemWindowInsetBottom());
            }
            return ins;
        });

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setGeolocationEnabled(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setUserAgentString(s.getUserAgentString() + " EducaJaApp/1.0");

        web.addJavascriptInterface(new Ponte(), "EducaJaAndroid");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest pedido) {
                Uri u = pedido.getUrl();
                if (interno(u)) return false;
                abrirFora(u);
                return true;
            }

            @Override
            public void onReceivedError(WebView v, WebResourceRequest pedido, WebResourceError erro) {
                if (pedido.isForMainFrame()) {
                    v.loadDataWithBaseURL(SITE, paginaSemInternet(), "text/html", "utf-8", null);
                }
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onGeolocationPermissionsShowPrompt(String origem, GeolocationPermissions.Callback cb) {
                if (temLocalizacao()) {
                    cb.invoke(origem, true, false);
                } else {
                    geoOrigem = origem;
                    geoCallback = cb;
                    requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION}, PEDIDO_LOCAL);
                }
            }
        });

        if (salvo != null) web.restoreState(salvo);
        else web.loadUrl(SITE);
    }

    private boolean interno(Uri u) {
        String esquema = u.getScheme();
        if ("about".equals(esquema) || "data".equals(esquema) || "blob".equals(esquema)) return true;
        String caminho = u.getPath() == null ? "" : u.getPath();
        return "https".equals(esquema) && (HOST.equalsIgnoreCase(u.getHost()) || HOST_ANTIGO.equalsIgnoreCase(u.getHost())) && caminho.startsWith(CAMINHO);
    }

    /** Telefone, WhatsApp, mapas e sites de fora abrem no app certo do celular. */
    private void abrirFora(Uri u) {
        try {
            Intent i;
            if ("intent".equals(u.getScheme())) {
                i = Intent.parseUri(u.toString(), Intent.URI_INTENT_SCHEME);
            } else {
                i = new Intent(Intent.ACTION_VIEW, u);
            }
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
        } catch (ActivityNotFoundException | java.net.URISyntaxException e) {
            Toast.makeText(this, "Nenhum app encontrado para abrir este link.", Toast.LENGTH_SHORT).show();
        }
    }

    private boolean temLocalizacao() {
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    @Override
    public void onRequestPermissionsResult(int codigo, String[] permissoes, int[] resultados) {
        super.onRequestPermissionsResult(codigo, permissoes, resultados);
        if (codigo == PEDIDO_LOCAL && geoCallback != null) {
            geoCallback.invoke(geoOrigem, temLocalizacao(), false);
            geoCallback = null;
            geoOrigem = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onSaveInstanceState(Bundle estado) {
        super.onSaveInstanceState(estado);
        web.saveState(estado);
    }

    @Override
    protected void onPause() {
        web.onPause();
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
    }

    private String paginaSemInternet() {
        return "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                + "<style>body{font-family:sans-serif;background:#F4F6F8;color:#16204F;display:grid;place-items:center;min-height:90vh;margin:0;padding:24px;text-align:center}"
                + "b{display:block;font-size:20px;margin-bottom:8px}button{margin-top:18px;background:#1C2A78;color:#fff;border:0;border-radius:10px;padding:12px 22px;font-size:16px}</style></head>"
                + "<body><div><b>Sem conexão</b>Conecte-se à internet para abrir o Educa Já pela primeira vez.<br>Depois disso, os últimos dados ficam guardados no celular."
                + "<br><button onclick=\"location.href='" + SITE + "'\">Tentar de novo</button></div></body></html>";
    }

    /** Recebe os arquivos (CSV) gerados pelo site e salva na pasta Downloads do celular. */
    private class Ponte {
        @JavascriptInterface
        public void salvar(String nome, String base64, String tipo) {
            try {
                byte[] dados = Base64.decode(base64, Base64.DEFAULT);
                Uri destino;
                String onde;
                if (Build.VERSION.SDK_INT >= 29) {
                    ContentResolver r = getContentResolver();
                    ContentValues cv = new ContentValues();
                    cv.put(MediaStore.MediaColumns.DISPLAY_NAME, nome);
                    cv.put(MediaStore.MediaColumns.MIME_TYPE, tipo == null || tipo.isEmpty() ? "application/octet-stream" : tipo);
                    cv.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/Educa Ja");
                    destino = r.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                    if (destino == null) throw new Exception("sem destino");
                    try (OutputStream out = r.openOutputStream(destino)) { out.write(dados); }
                    onde = "Downloads/Educa Ja";
                } else {
                    File pasta = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
                    File arq = new File(pasta, nome);
                    try (OutputStream out = new FileOutputStream(arq)) { out.write(dados); }
                    destino = null;
                    onde = arq.getParent();
                }
                final String msg = "Arquivo salvo em " + onde;
                final Uri abrir = destino;
                final String mime = tipo;
                runOnUiThread(() -> {
                    Toast.makeText(MainActivity.this, msg, Toast.LENGTH_LONG).show();
                    if (abrir != null) {
                        try {
                            Intent i = new Intent(Intent.ACTION_VIEW);
                            i.setDataAndType(abrir, mime);
                            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                            startActivity(i);
                        } catch (Exception ignorado) { /* sem app para abrir: fica só salvo */ }
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "Não foi possível salvar o arquivo.", Toast.LENGTH_LONG).show());
            }
        }
    }
}
