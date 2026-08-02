/* พฤติกรรมฝั่ง client ทั้งหมดของแอป
 *
 * **ห้ามมี inline handler (onclick/onsubmit/onchange) ใน template**
 * CSP ของเราไม่มี 'unsafe-inline' — inline handler จะถูก browser บล็อกเงียบ ๆ
 * และ template จะพังโดยไม่มี error ฝั่ง server ให้เห็น
 *
 * ทุกอย่างใช้ event delegation ที่ document เดียว จึงทำงานกับ element
 * ที่ render มาทีหลังด้วย และไม่ต้องผูก listener ต่อแถว
 *
 * สัญญากับ template:
 *   data-confirm="ข้อความ"  บน <form>  -> ถามยืนยันก่อน submit
 *   data-auto-submit        บน control -> เปลี่ยนค่าแล้ว submit ฟอร์มทันที
 *   class="js-hidden"       บน element -> ซ่อนเมื่อ JS ทำงาน (fallback ตอนไม่มี JS)
 */
(function () {
  "use strict";

  /* ประกาศว่า JS ทำงานแล้ว ให้ CSS ซ่อนปุ่ม fallback ได้
   * ตั้งเป็นอย่างแรกสุด ก่อน render เสร็จ จะได้ไม่เห็นปุ่มกะพริบ */
  document.documentElement.classList.add("js");

  document.addEventListener("submit", function (event) {
    var form = event.target.closest("form[data-confirm]");
    if (form && !window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });

  document.addEventListener("change", function (event) {
    var control = event.target.closest("[data-auto-submit]");
    if (control && control.form) {
      control.form.requestSubmit
        ? control.form.requestSubmit()
        : control.form.submit();
    }
  });
})();
