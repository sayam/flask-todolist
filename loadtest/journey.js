// ชุด load test ที่เดินเส้นทางจริงของผู้ใช้ (Phase 6 · P6-03 — ดู ADR 0031)
//
// **ไม่ยิงหน้าเดียวซ้ำ ๆ** เพราะตัวเลขที่ได้จะเป็นของ cache ของ template กับ
// ของ query ที่ฐานข้อมูลเพิ่งตอบไป ไม่ใช่ของงานที่ผู้ใช้ทำจริง — เส้นทางนี้
// ครอบทั้งการอ่านรายการ, ตัวกรองตามวัน (query ที่ P6-05 ต้องไปทบทวน),
// การเปิดหน้าแก้ไข และการเขียน
//
// **login ทำครั้งเดียวต่อ VU ไม่ใช่ทุกรอบ** — การแฮชรหัสผ่านถูกออกแบบมาให้ช้า
// โดยตั้งใจ (scrypt) ถ้านับรวมทุกรอบ ตัวเลขทั้งชุดจะกลายเป็นการวัดความเร็ว
// ของ scrypt ไม่ใช่ของแอป · ผู้ใช้จริงก็ login วันละครั้งแล้วใช้ทั้งวันเหมือนกัน
//
// รัน:
//   docker run --rm -i --network host -e BASE_URL=http://127.0.0.1:8000 \
//     -e VUS=5 -e DURATION=30s grafana/k6 run - < loadtest/journey.js

import http from "k6/http";
import { check, sleep, fail } from "k6";
import { Trend } from "k6/metrics";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000";
const USERNAME = __ENV.TODOLIST_USER || "loadtest";
// **รหัสต้องไม่มีชื่อผู้ใช้อยู่ข้างใน** — นโยบายรหัสผ่านของแอปปฏิเสธแบบนั้น
// (ADR 0019) ตอนแรกตั้งเป็น `loadtest-...` สำหรับผู้ใช้ `loadtest` แล้ว
// `create-user` ปฏิเสธเงียบ ๆ ส่วน k6 รายงานว่า login ไม่ผ่าน 960 ครั้ง
const PASSWORD = __ENV.TODOLIST_PASSWORD || "k6-journey-passphrase-not-a-secret";

// เวลาที่ผู้ใช้รอในแต่ละหน้า แยกจากกันเพื่อให้รู้ว่า *อะไร* ช้า ไม่ใช่แค่ "ช้า"
const listing = new Trend("page_listing", true);
const filtered = new Trend("page_filtered", true);
const editForm = new Trend("page_edit_form", true);
const creating = new Trend("page_create", true);

export const options = {
  vus: Number(__ENV.VUS || 5),
  duration: __ENV.DURATION || "30s",
  // **ต้องขอ p(99) เอง** — สรุปผลของ k6 ให้แค่ถึง p(95) โดยปริยาย ส่วน
  // threshold คำนวณแยกต่างหาก จึงเห็น p(99) ตอนตั้งเกณฑ์แต่ไม่เห็นในสรุป
  // (เจอตอนไล่เส้นโค้ง: `KeyError: 'p99'` ทั้งที่ตัวเลขโผล่ในรอบก่อนหน้า)
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
  // **เกณฑ์นี้คือเป้าของ ADR 0031** — ตั้งไว้ที่นี่เพื่อให้ k6 ตัดสินเองว่า
  // ผ่านหรือไม่ ไม่ต้องมีคนมานั่งอ่านตัวเลขแล้วเถียงกันทีหลัง
  // ปิดได้ด้วย NO_THRESHOLDS=1 ตอนไล่หาจุดที่ระบบเริ่มพัง (ซึ่งต้อง "ไม่ผ่าน"
  // เป็นเรื่องปกติ — ดู scripts/loadtest_curve.sh)
  thresholds: __ENV.NO_THRESHOLDS
    ? {}
    : {
        "http_req_duration{expected_response:true}": ["p(95)<200", "p(99)<500"],
        http_req_failed: ["rate<0.01"],
      },
};

// ตัวแปรระดับโมดูล = **หนึ่งชุดต่อ VU** (k6 สร้าง instance แยกให้แต่ละตัว)
let signedIn = false;

function csrfFrom(body) {
  const found = body.match(/name="csrf_token"[^>]*value="([^"]+)"/);
  return found ? found[1] : null;
}

function signIn() {
  const page = http.get(`${BASE}/login`);
  const token = csrfFrom(page.body);
  if (!token) {
    fail("ไม่เจอ csrf_token ในหน้า login — แอปตอบอะไรกลับมาไม่ทราบ");
  }
  // **`redirects: 0` สำคัญ** — k6 ตามการ redirect ให้เองโดยปริยาย ทำให้
  // `status` ที่ได้เป็น 200 ของหน้าปลายทาง ไม่ใช่ 302 ที่บอกว่า login สำเร็จ
  // (เจอจริง: เช็คว่า === 302 แล้วล้ม 100% ตั้งแต่ครั้งแรก ทั้งที่ curl ได้ 302)
  const response = http.post(
    `${BASE}/login`,
    { username: USERNAME, password: PASSWORD, csrf_token: token },
    { redirects: 0 },
  );
  // 302 = สำเร็จ · 200 = กลับมาหน้า login พร้อมข้อความว่าผิด
  if (!check(response, { "login ผ่าน": (r) => r.status === 302 })) {
    fail(`login ไม่ผ่าน (${response.status}) — ตรวจว่าสร้างผู้ใช้ ${USERNAME} แล้วหรือยัง`);
  }
}

export default function () {
  if (!signedIn) {
    signIn();
    signedIn = true;
  }

  // 1. หน้ารายการงาน — หน้าที่ผู้ใช้เปิดบ่อยที่สุด
  let response = http.get(`${BASE}/`);
  listing.add(response.timings.duration);
  check(response, { "รายการงานตอบ 200": (r) => r.status === 200 });

  // 2. ตัวกรองตามวัน — query ที่ซับซ้อนที่สุดของแอป (ช่วงเวลา + user_id)
  response = http.get(`${BASE}/?when=today`);
  filtered.add(response.timings.duration);
  check(response, { "ตัวกรองตอบ 200": (r) => r.status === 200 });

  // 3. เปิดหน้าเพิ่มงาน แล้วเขียนจริงหนึ่งครั้ง
  //    **เขียนน้อยกว่าอ่านโดยตั้งใจ** ให้ใกล้เคียงการใช้งานจริง และเพื่อไม่ให้
  //    ฐานข้อมูลโตเร็วจนตัวเลขของแต่ละรอบเทียบกันไม่ได้
  const form = http.get(`${BASE}/`);
  const token = csrfFrom(form.body);
  if (token) {
    response = http.post(
      `${BASE}/add`,
      { title: `งานจาก load test ${__VU}-${__ITER}`, csrf_token: token },
      { redirects: 0 },
    );
    creating.add(response.timings.duration);
    check(response, { "เพิ่มงานสำเร็จ": (r) => r.status === 302 });
  }

  // 4. หน้าแก้ไข — อ่านงานหนึ่งชิ้นตาม id
  response = http.get(`${BASE}/edit/1`);
  editForm.add(response.timings.duration);
  check(response, { "หน้าแก้ไขตอบได้": (r) => r.status === 200 || r.status === 404 });

  // ผู้ใช้จริงไม่ได้กดรัว ๆ — เว้นจังหวะให้เหมือนคนอ่านหน้าจอก่อนกดต่อ
  sleep(1);
}

// **สรุปผลเป็น JSON บรรทัดเดียวเมื่อขอ** — `--summary-export` ให้ผลที่ปนกับ
// output อื่นจนแยกไม่ออก (เจอจริงตอนไล่เส้นโค้ง) ส่วน `handleSummary` เป็น
// ทางที่ k6 ให้ควบคุมเองทั้งหมด และไม่ขึ้นกับเวอร์ชันของ flag
export function handleSummary(data) {
  if (!__ENV.SUMMARY_JSON) {
    return {};
  }
  const duration = data.metrics.http_req_duration.values;
  return {
    stdout: JSON.stringify({
      vus: Number(__ENV.VUS || 5),
      p95: duration["p(95)"],
      p99: duration["p(99)"],
      rps: data.metrics.http_reqs.values.rate,
      failed: (data.metrics.http_req_failed?.values?.rate ?? 0) * 100,
    }) + "\n",
  };
}
