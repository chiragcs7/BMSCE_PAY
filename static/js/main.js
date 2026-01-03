document.addEventListener("DOMContentLoaded", () => {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const rows = document.querySelectorAll("#history-table tbody tr");
  const toggleBtn = document.getElementById("sidebarToggle");
  const sidebar = document.querySelector(".paytm-sidebar");
  const appShell = document.querySelector(".app-shell");

  // Sidebar collapse / expand
  if (toggleBtn && sidebar && appShell) {
    toggleBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
      appShell.classList.toggle("sidebar-collapsed");
    });
  }

  // History range filter (All / This month / This year)
  if (tabBtns.length && rows.length) {
    tabBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        tabBtns.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");

        const range = btn.dataset.range;
        const now = new Date();

        rows.forEach((r) => {
          const ts = new Date(r.dataset.ts);
          let show = true;

          if (range === "month") {
            show =
              ts.getMonth() === now.getMonth() &&
              ts.getFullYear() === now.getFullYear();
          } else if (range === "year") {
            show = ts.getFullYear() === now.getFullYear();
          }

          r.style.display = show ? "" : "none";
        });
      });
    });
  }
});
