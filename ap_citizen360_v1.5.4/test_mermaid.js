const puppeteer = require('puppeteer');
(async () => {
    const browser = await puppeteer.launch();
    const page = await browser.newPage();
    page.on('console', msg => console.log('PAGE LOG:', msg.text()));
    page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
    await page.goto('file:///Users/prakhar/Downloads/Student_Dropout_v1.3.1/ap_citizen360_v1.5.4/conversational_query_engine_architecture.html');
    await page.waitForTimeout(2000);
    await browser.close();
})();
