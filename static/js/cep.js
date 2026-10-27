(() => {
  const cepField = document.getElementById("id_postal_code");
  const status = document.getElementById("cep-status");
  const form = cepField?.form;
  if (!cepField || !status || !form) return;

  const addressFields = {
    street: document.getElementById("id_street"),
    neighborhood: document.getElementById("id_neighborhood"),
    city: document.getElementById("id_city"),
    state: document.getElementById("id_state"),
  };
  const submitButton = form.querySelector('button[type="submit"]');
  let debounceTimer;
  let requestController;
  let requestNumber = 0;

  const showStatus = (message, type = "") => {
    status.textContent = message;
    status.classList.toggle("is-error", type === "error");
    status.classList.toggle("is-success", type === "success");
  };

  const lookupCep = async (digits) => {
    const currentRequest = ++requestNumber;
    requestController?.abort();
    const controller = new AbortController();
    requestController = controller;
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    if (submitButton) submitButton.disabled = true;
    showStatus("Consultando CEP...");

    try {
      const response = await fetch(
        `https://viacep.com.br/ws/${digits}/json/`,
        {
          headers: { Accept: "application/json" },
          signal: controller.signal,
        },
      );
      if (!response.ok) throw new Error("O serviço de CEP não respondeu.");

      const data = await response.json();
      if (currentRequest !== requestNumber) return;
      if (data.erro) {
        showStatus("CEP não encontrado. Confira o número ou preencha o endereço manualmente.", "error");
        return;
      }

      addressFields.street.value = data.logradouro || "";
      addressFields.neighborhood.value = data.bairro || "";
      addressFields.city.value = data.localidade || "";
      addressFields.state.value = data.uf || "";
      showStatus("Endereço preenchido. Confira os dados e informe número/complemento.", "success");
    } catch (error) {
      if (currentRequest !== requestNumber) return;
      showStatus(
        "Não foi possível consultar o CEP. Verifique a conexão ou preencha o endereço manualmente.",
        "error",
      );
    } finally {
      window.clearTimeout(timeout);
      if (currentRequest === requestNumber && submitButton) {
        submitButton.disabled = false;
      }
    }
  };

  cepField.addEventListener("input", () => {
    const digits = cepField.value.replace(/\D/g, "").slice(0, 8);
    cepField.value = digits.length > 5
      ? `${digits.slice(0, 5)}-${digits.slice(5)}`
      : digits;

    clearTimeout(debounceTimer);
    requestNumber += 1;
    requestController?.abort();
    if (submitButton) submitButton.disabled = false;

    if (digits.length !== 8) {
      showStatus(
        digits.length === 0
          ? "Digite o CEP para preencher o endereço automaticamente."
          : "Digite os 8 números do CEP.",
      );
      return;
    }

    if (submitButton) submitButton.disabled = true;
    showStatus("CEP completo. Consultando endereço...");
    debounceTimer = window.setTimeout(() => lookupCep(digits), 350);
  });
})();
