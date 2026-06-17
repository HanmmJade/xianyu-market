// Frida SSL Pinning绕过脚本
// 用于拦截闲鱼App的HTTPS请求

console.log("[*] 闲鱼SSL Pinning绕过脚本已加载");

// 绕过Android系统级SSL Pinning
Java.perform(function() {
    console.log("[*] 开始Hook Android SSL...");
    
    // 绕过TrustManagerImpl
    try {
        var TrustManagerImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
        TrustManagerImpl.verifyChain.implementation = function(untrustedChain, trustAnchorChain, host, clientAuth, ocspData, tlsSctData) {
            console.log("[+] 绕过SSL验证: " + host);
            return untrustedChain;
        };
        console.log("[+] TrustManagerImpl Hook成功");
    } catch (e) {
        console.log("[-] TrustManagerImpl Hook失败: " + e);
    }
    
    // 绕过OkHttp CertificatePinner
    try {
        var CertificatePinner = Java.use('okhttp3.CertificatePinner');
        CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function(hostname, peerCertificates) {
            console.log("[+] 绕过OkHttp证书验证: " + hostname);
            return;
        };
        console.log("[+] CertificatePinner Hook成功");
    } catch (e) {
        console.log("[-] CertificatePinner Hook失败: " + e);
    }
});

// Hook闲鱼API签名函数
Java.perform(function() {
    console.log("[*] 开始Hook闲鱼API签名...");
    
    // 尝试Hook常见的签名类
    var signClasses = [
        'com.taobao.idlefish.utils.SignUtils',
        'com.taobao.idlefish.security.SignHelper',
        'com.taobao.idlefish.mtop.SignManager',
        'com.taobao.idlefish.network.SignInterceptor',
    ];
    
    signClasses.forEach(function(className) {
        try {
            var SignClass = Java.use(className);
            console.log("[+] 找到签名类: " + className);
            
            // Hook所有方法
            var methods = SignClass.class.getDeclaredMethods();
            methods.forEach(function(method) {
                var methodName = method.getName();
                console.log("    方法: " + methodName);
                
                try {
                    SignClass[methodName].overload('java.lang.String').implementation = function(param) {
                        var result = this[methodName](param);
                        console.log("[+] 签名调用: " + className + "." + methodName);
                        console.log("    参数: " + param);
                        console.log("    结果: " + result);
                        
                        // 发送到PC端
                        send({
                            type: 'sign',
                            class: className,
                            method: methodName,
                            param: param,
                            result: result
                        });
                        
                        return result;
                    };
                } catch (e) {
                    // 方法签名不匹配，跳过
                }
            });
        } catch (e) {
            // 类不存在，跳过
        }
    });
});

// Hook MTOP请求
Java.perform(function() {
    console.log("[*] 开始Hook MTOP请求...");
    
    try {
        var MtopRequest = Java.use('mtopsdk.mtop.domain.MtopRequest');
        MtopRequest.setApiName.implementation = function(apiName) {
            console.log("[+] MTOP API: " + apiName);
            this.setApiName(apiName);
        };
        
        MtopRequest.setData.implementation = function(data) {
            console.log("[+] MTOP Data: " + data);
            this.setData(data);
        };
        
        console.log("[+] MtopRequest Hook成功");
    } catch (e) {
        console.log("[-] MtopRequest Hook失败: " + e);
    }
});

console.log("[*] SSL Pinning绕过脚本加载完成");
