// maoyan_grab.js — 猫眼抢票 AutoX.js 脚本
// 使用前：安卓设备安装猫眼 App + AutoX.js
// 手动登录猫眼，进入目标演出详情页，再运行此脚本

"auto";

// ==================== 配置区 ====================
var CONFIG = {
    targetPrice: "2380",
    targetSession: "周六",
    viewerName: "",
    saleTime: "2026-04-01 10:00:00",
    maxRetry: 50,
    clickInterval: 80,
};

// ==================== 工具函数 ====================
function log(msg) {
    console.log("[猫眼抢票] " + msg);
    toast(msg);
}

function clickElement(selector, timeout) {
    timeout = timeout || 3000;
    var el = selector.findOne(timeout);
    if (el) {
        var b = el.bounds();
        click(b.centerX(), b.centerY());
        log("点击: " + (el.text() || el.desc()));
        return true;
    }
    return false;
}

function waitAndClick(textStr, timeout) {
    timeout = timeout || 5000;
    return clickElement(textContains(textStr), timeout);
}

function getSaleTimestamp() {
    var parts = CONFIG.saleTime.split(/[- :]/);
    var d = new Date(parts[0], parts[1] - 1, parts[2],
                     parts[3], parts[4], parts[5]);
    return d.getTime();
}

// ==================== 主流程 ====================
function main() {
    auto.waitFor();
    log("无障碍服务已启用");

    var saleTs = getSaleTimestamp();
    var now = new Date().getTime();
    var waitMs = saleTs - now - 2000;
    if (waitMs > 0) {
        log("等待开售，还有 " + Math.round(waitMs / 1000) + " 秒");
        sleep(waitMs);
        log("进入抢票倒计时！");
    }

    while (new Date().getTime() < saleTs) {
        sleep(10);
    }
    log("开售！开始抢票！");

    for (var i = 0; i < CONFIG.maxRetry; i++) {
        if (clickElement(textContains("立即购票"), 500) ||
            clickElement(textContains("选座购买"), 500) ||
            clickElement(textContains("立即预订"), 500)) {
            log("已点击购票按钮");
            sleep(CONFIG.clickInterval);
        }

        if (clickElement(textContains(CONFIG.targetPrice), 500)) {
            log("已选择票价: " + CONFIG.targetPrice);
            sleep(CONFIG.clickInterval);
        }

        if (CONFIG.targetSession &&
            clickElement(textContains(CONFIG.targetSession), 300)) {
            log("已选择场次: " + CONFIG.targetSession);
            sleep(CONFIG.clickInterval);
        }

        if (clickElement(textContains("选好了"), 500) ||
            clickElement(textContains("确认"), 500)) {
            log("已确认选座");
            sleep(CONFIG.clickInterval);
        }

        if (CONFIG.viewerName) {
            clickElement(textContains(CONFIG.viewerName), 300);
        } else {
            var viewer = className("android.widget.CheckBox").findOne(500);
            if (viewer && !viewer.checked()) {
                var vb = viewer.bounds();
                click(vb.centerX(), vb.centerY());
                log("已选择观演人");
            }
        }

        if (clickElement(textContains("提交订单"), 500) ||
            clickElement(textContains("确认订单"), 500)) {
            log("已提交订单！");
            sleep(CONFIG.clickInterval);
        }

        if (textContains("去支付").findOne(300) ||
            textContains("待支付").findOne(300)) {
            log("=== 抢票成功！请手动完成支付 ===");
            break;
        }

        if (textContains("已售罄").findOne(200) ||
            textContains("缺货").findOne(200)) {
            log("暂时无票，返回重试 #" + (i + 1));
            back();
            sleep(200);
        }

        sleep(CONFIG.clickInterval);
    }
}

try {
    main();
} catch (e) {
    log("异常: " + e);
}
