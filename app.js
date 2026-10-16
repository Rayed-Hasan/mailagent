const filters = document.querySelectorAll(".filter");
const messages = document.querySelectorAll(".mail-item");
const toast = document.querySelector("#toast");
const palette = document.querySelector("#commandPalette");
const paletteInput = document.querySelector("#paletteInput");

filters.forEach((filter) => {
  filter.addEventListener("click", () => {
    filters.forEach((item) => item.classList.remove("active"));
    filter.classList.add("active");
    const selected = filter.dataset.filter;
    messages.forEach((message) => {
      message.hidden = selected !== "all" && message.dataset.category !== selected;
    });
  });
});

function showToast(message) {
  toast.innerHTML = `<span>✦</span> ${message}`;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 3200);
}

document.querySelector("#reviewButton").addEventListener("click", () => {
  document.querySelector(".focus-card").scrollIntoView({ behavior: "smooth", block: "center" });
  showToast("Alex has your morning brief ready.");
});

document.querySelector("#openBrief").addEventListener("click", () => {
  showToast("Your 3-minute morning brief is ready to review.");
});

function togglePalette(open) {
  if (!open && document.activeElement === paletteInput) paletteInput.blur();
  palette.classList.toggle("open", open);
  palette.setAttribute("aria-hidden", String(!open));
  if (open) window.setTimeout(() => paletteInput.focus(), 0);
}

document.querySelector(".icon-button[aria-label='Search']").addEventListener("click", () => togglePalette(true));
document.querySelector(".palette-backdrop").addEventListener("click", () => togglePalette(false));
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    togglePalette(true);
  }
  if (event.key === "Escape") togglePalette(false);
});

document.querySelector("#modeButton").addEventListener("click", () => {
  showToast("Approve mode is on — nothing sends without your check.");
});

document.querySelectorAll(".mail-check").forEach((checkbox) => {
  checkbox.addEventListener("click", () => {
    checkbox.style.background = checkbox.style.background ? "" : "#7065de";
    checkbox.style.borderColor = checkbox.style.borderColor ? "" : "#7065de";
    checkbox.textContent = checkbox.textContent ? "" : "✓";
    checkbox.style.color = "#fff";
    checkbox.style.fontSize = "10px";
    checkbox.style.display = "grid";
    checkbox.style.placeItems = "center";
  });
});
