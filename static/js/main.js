document.addEventListener("DOMContentLoaded", () => {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const rows = document.querySelectorAll("#history-table tbody tr");

  if (tabBtns.length && rows.length) {
    tabBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        tabBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const range = btn.dataset.range;
        const now = new Date();

        rows.forEach(r => {
          const ts = new Date(r.dataset.ts);
          let show = true;

          if (range === "month") {
            show = ts.getMonth() === now.getMonth() && ts.getFullYear() === now.getFullYear();
          } else if (range === "year") {
            show = ts.getFullYear() === now.getFullYear();
          }
          r.style.display = show ? "" : "none";
        });
      });
    });
  }
});
