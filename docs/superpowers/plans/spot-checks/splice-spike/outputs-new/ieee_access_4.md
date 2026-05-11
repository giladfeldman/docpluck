# Latent Denoising Diffusion GAN: Faster sampling, Higher image quality
Luan Thanh Trinh, Tomoki Hamagami Yokohama National University

## Abstract

Diffusion models are emerging as powerful solutions for generating high-fidelity and diverse images, often surpassing GANs under many circumstances. However, their slow inference speed hinders their potential for real-time applications. To address this, DiffusionGAN leveraged a conditional GAN to drastically reduce the denoising steps and speed up inference. Its advancement, Wavelet Diffusion, further accelerated the process by converting data into wavelet space, thus enhancing efficiency. Nonetheless, these models still fall short of GANs in terms of speed and image quality. To bridge these gaps, this paper introduces the Latent Denoising Diffusion GAN, which employs pretrained autoencoders to compress images into a compact latent space, significantly improving inference speed and image quality. Furthermore, we propose a Weighted Learning strategy to enhance diversity and image quality. Experimental results on the CIFAR-10, CelebA-HQ, and LSUNChurch datasets prove that our model achieves state-ofthe-art running speed among diffusion models. Compared to its predecessors, DiffusionGAN and Wavelet Diffusion, our model shows remarkable improvements in all evaluation metrics. Code and pre-trained checkpoints: https: //github.com/thanhluantrinh/LDDGAN.git

## Introduction

Despite being a recent introduction, diffusion models have quickly established themselves as a pivotal paradigm for image-generation tasks. At their core, diffusion models hinge on two crucial processes: the forward process (or diffusion process) and the reverse process (denoising process). In the forward process, Gaussian noise is incrementally infused into the input image until it transforms into an isotropic Gaussian. Conversely, in the reverse process, a model is meticulously trained to invert the forward process and faithfully reproduce the original input image. After training, the power of diffusion models shines as we can generate high quality images by navigating randomly sampled noise through the adeptly learned denoising process.

In comparison to other prominent deep generative models, diffusion models distinguish themselves through the excellence of the generated images in terms of quality and diversity, coupled with their inherent training stability. Particularly noteworthy is the observation that diffusion models have surpassed Generative Adversarial Networks (GANs), which have dominated the image generation task in recent years, excelling in both image quality ( [1, 2]) and diversity ( [3, 4, 49]). One notable aspect heightening expectations for diffusion models is their growing capacity to effectively incorporate various conditional inputs, such as semantic maps, text, representations, and images. This versatility expands the potential applications of diffusion models into areas like text-to-image generation ( [2, 5, 30]), video generation ( [8, 10]), image-to-image translation ( [6, 7, 9]), text-to-3D generation [11], and beyond.
Despite their considerable potential, the hindrance of slow inference speed poses a significant obstacle for diffusion models in becoming fully-fledged image generation models that can meet diverse expectations across various domains, particularly in real-time applications. The fundamental cause of slow sampling in these models lies in the Gaussian assumption made during the denoising step, an assumption that is valid only for small step sizes. Consequently, diffusion models often necessitate a substantial number of denoising steps, typically ranging in the hundreds or thousands. By modeling complex and multimodal distributions through conditional GANs, DiffusionGAN [28] enables larger denoising steps, reducing the number of denoising steps to just a few, thereby significantly accelerating the inference time of diffusion models. Wavelet Diffusion [29], an enhancement of DiffusionGAN, achieves a further increase in inference speed by transferring data from pixel space to wavelet space, reducing the input data size by a factor of 4 and becoming the fastest existing diffusion model. However, Wavelet Diffusion still lags considerably behind StyleGAN [60]. Additionally, the acceleration of inference speed shows signs of compromising the output image quality, as the output quality of both DiffusionGAN and Wavelet Diffusion is lower than that of StyleGAN and other recent diffusion models.

This paper aims to bridge both the gap in image quality and the gap in speed by introducing the Latent Denoising Diffusion GAN (LDDGAN). Firstly, instead of residing in a high-dimensional pixel space, input images are compressed as much as possible into a low-dimensional latent space through pre-trained autoencoders. This compression significantly reduces computational costs during both training and inference, facilitating faster sampling. Given that the latent space is more suitable for diffusion models than the high-dimensional pixel space [30], our approach aims to enhance both image quality and sample diversity by utilizing this space for both the diffusion and denoising processes. Following the principles of DiffusionGAN, a conditional GAN is employed to model complex and multimodal distributions and enable a large denoising step. Additionally, to enhance diversity through adversarial loss while leveraging the effect of reconstruction loss for image quality improvement, we propose a novel learning strategy called Weighted Learning. Since our model primarily uses multimodal distributions, instead of restricting latents learned by the autoencoder to Gaussian distributions as in other latent-based models ( [13, 30, 45]), we allow the autoencoder to freely search for the appropriate latent space. This approach helps to significantly accelerate the convergence of the autoencoder and improve the overall quality and diversity of the main model.
Based on experimental results on standard benchmarks including CIFAR-10, CELEBA-HQ, and LSUN Church, our model achieves state-of-the-art running speed for a diffusion model while maintaining high image quality. When compared to GANs, we achieve comparable image generation quality and running speed, along with increased diversity. Additionally, in comparison to two predecessors, DiffusionGAN and Wavelet Diffusion, our model significantly outperforms them across the majority of comparison metrics.
In summary, our contributions are as follows:
• We propose a novel Latent Denoising Diffusion GAN framework that leverages dimensionality reduction and the high compatibility of low-dimensional latent spaces with the diffusion model’s denoising process. This approach not only improves inference speed and the quality of generated images but also enhances diversity.
• We find that if the denoising process of a diffusion model does not depend on Gaussian distributions, it becomes necessary to eliminate the autoencoder’s learned dependency on the Gaussian distribution to enhance the diversity and quality of the generated images. This insight could serve as a recommendation for future latent-based diffusion models.
• We propose an innovative Weighted Learning strategy

that boosts diversity through adversarial loss, while also improving image quality via the effect of reconstruction loss.
• Our Latent Denoising Diffusion GAN features low training costs and state-of-the-art inference speeds, paving the way for real-time, high-fidelity diffusion models.

## Related Work

2.1. Image Generation models
GANs (Generative Adversarial Networks, [12]) are among the representative generative models extensively utilized in various real-time applications due to their ability to rapidly generate high-quality images [17]. However, challenges in optimization ( [16,18,19]) and difficulty in capturing the full data distribution [20] represent two main weaknesses of GANs. In contrast, Variational Autoencoders (VAEs, [13]) and flow-based models ( [14, 15]) excel in fast inference speed and high sample diversity but face challenges in generating high-quality images. Recently, diffusion models have been introduced and have quickly made an impressive impact by achieving state-of-the-art results in both sample diversity [4] and sample quality [21]. One of the two primary weaknesses of diffusion models, high training costs, has been effectively addressed by Latent Diffusion Models (LDMs, [30]). This was achieved by shifting the diffusion process from the pixel space to the latent space using pre-trained autoencoders. Despite the similarity between this approach and ours in using latent space, their reliance on Gaussian distributions in both the denoising process and the latent space learned by the autoencoder necessitates thousands of network evaluations during the sampling process. This dependency results in slow inference speeds, representing the primary remaining weakness of diffusion models. Consequently, it becomes a significant bottleneck, restricting the practical use of diffusion models in real-time applications.
2.2. Faster Diffusion Models
To enhance the inference speed of diffusion models, several methods have been proposed, including learning an adaptive noise schedule [22], using non-Markovian diffusion processes [47, 55], and employing improved SDE solvers for continuous-time models [23]. However, these methods either experience notable deterioration in sample quality or still necessitate a considerable number of sampling steps. Studies on knowledge distillation [57, 69, 70] are also worth noting, as in some cases, they can perform the diffusion process with just a few steps or even just one step and produce high-quality images. The weakness of the knowledge distillation method is that it requires a well-pretrained diffusion model to be used as a teacher model for

the main model (student model). The results of the student model often struggle to surpass the teacher model due to this student-teacher constraint.
The most successful method to date for accelerating inference speed without compromising image quality, and without relying on another pre-trained diffusion model, is DiffusionGAN [28]. By modeling complex and multimodal distributions through conditional GANs, DiffusionGAN enables larger denoising steps, reducing the number of denoising steps to just a few and significantly accelerating the inference process. Wavelet Diffusion [29], an enhancement of DiffusionGAN, achieves a further increase in inference speed by transferring data from pixel space to wavelet space, reducing the input data size by a factor of 4 and becoming the fastest existing diffusion model. However, the inference speed of Wavelet Diffusion is still much slower than that of traditional GANs, and the trade-off between sampling speed and quality still requires further improvement. We aim to address both problems by utilizing latent space.
2.3. Latent-based approaches
Regarding diffusion model families, similar to our approach, LDMs in [30] and Score-based generative models (SGMs) in [45] utilize an autoencoder to transform data from pixel space to latent space and conduct the diffusion process in this space. However, as mentioned above, their dependence on Gaussian distributions in both the denoising process and the latent space learned by the autoencoder results in the necessity for thousands of network evaluations during the sampling process. This dependency leads to slow inference speeds. Our method enables larger denoising steps, thereby reducing the number of denoising steps to just a few and significantly accelerating the inference speed. Additionally, due to the absence of a reliance on Gaussian distribution, unlike LDMs and SGMs, our autoencoders are free to explore potential latent spaces rather than attempting to model spaces with Gaussian distribution. Details about our autoencoders are described in Section 4.2.

## Background

Diffusion Models
The main idea of Diffusion models ( [30, 45, 47, 49]) lies in gradually adding noise to the data and then training a model to reverse that process gradually. In this way, the model becomes capable of generating data similar to the input data from pure Gaussian noise. The forward process, in which we gradually add noise to the input data x0, can be defined as follows:

q(x1:T |x0) = t≥1 q(x√t|xt−1), with q(xt|xt−1) = N (xt; 1 − βt, βtI)

(1)

where T and βt denote number of steps and pre-defined variance schedule at timesteps t, respectively. The reverse process, in which we remove noise from data, can be defined:

pθ(x0:T ) = p(xT ) t≥1 pθ(xt−1|xt), with pθ(xt−1|xt) = N (xt−1; µθ(xt, t), σt2I)

(2)

where µθ(xt, t) and σt2 are the mean and variance for the denoising model parameterized by θ. As introduced in [27],
the optimal mean can be defined as follows.

of small denoising steps (as highlighted by Sohl-Dickstein et al. in [25] and Feller in [26]). This necessitates a large

number of steps in the reverse process and causes a slow

sampling issue for diffusion models.

Denoising Diffusion GAN and Wavelet Diffusion

To reduce the inference time of diffusion models, it’s
crucial to significantly decrease the number of denoising diffusion steps T required for the reverse process. Addi-tionally, a new denoising method is required because us-ing large denoising steps causes the denoising distributions pθ(xt−1|xt) to become more complex and multimodal, unlike the existing diffusion models ( [30, 45, 47]) where the
denoising distributions follow a Gaussian distribution. To
overcome this challenge, DiffusionGAN models the denois-ing distribution with an complex and multimodal distribu-tion by using conditional GANs. Whereas existing diffusion models predict noise ϵ added to xt−1 at timestep t using xt, the generator Gθ(xt, z, t) in DiffusionGAN predicts the input data x0 with random latent variable z ∼ N (0, I). This crucial distinction allows DiffusionGAN’s denoising distribution pθ(xt−1|xt) to become multimodal and complex, unlike the unimodal denoising model of existing approaches. The perturbed sample x′t−1 is then acquired using pre-defined q(xt−1|xt, x0). The discriminator Dϕ performs judgment on fake pairts Dϕ(xt′−1, xt, t) and real pairs Dϕ(xt−1, xt, t).

Building upon Diffusion GAN, Wavelet Diffusion fur-

ther speeds up inference by performing denoising in wavelet

space rather than pixel space. It first decomposes the input image x ∈ R3×H×W into its low-frequency and high-

## Method

In this section, we begin by providing a comprehensive overview of the proposed framework, Latent Denoising Diffusion GAN (Section 4.1). Following this, we introduce the autoencoder utilized to train the main model (Section 4.2). Finally, we discuss the effect of reconstruction loss on the final result and introduce a novel training strategy called Weighted Learning (Section 4.3).

Figure 1. The training process of Latent Denoising Diffusion GAN (LDDGAN)
4.1. Latent Denoising Diffusion GAN
Figure 1 provides an overview of our proposed LDDGAN. A pre-trained encoder is used to compress input data X0 and transform it from pixel space to lowdimensional latent representation x0 = E(X0). It is important to note that the encoder downsamples the image by

a factor of f . We strive to compress the data as much as possible (using a larger f ), while still guaranteeing image quality upon decoding. Details about the autoencoder are described in Section 4.2.
The forward diffusion process and the reverse process are performed in low-dimensional latent space, rather than in wavelet space as in WDDGAN, or pixel space as in DDGAN and other inherent diffusion models. This method has two main advantages. Firstly, LDDGAN is capable of reducing the input image size by factors of 4, 8, or even more, unlike WDDGAN which can only reduce it by a factor of 4. This enhancement significantly increases the model’s inference speed and reduces computational costs. As investigated by Rombach et al. [30], compared to highdimensional pixel space, low-dimensional latent space is better suited for the diffusion model, a likelihood-based generative method. This results in improved quality and diversity of the generated samples.
In the latent space, to reduce inference time, the forward diffusion process is performed with a small number of sampling steps T (T ≤ 8), and each diffusion step has a significantly larger βt compared to traditional diffusion models. At timestep t, a corrupted sample xt is generated from the input sample x0 using the posterior distribution q(xt−1|x0). The generator G(xt, z, t) uses xt, the current timestep t, and a random latent variable z ∼ N (0, I) to predict an approximation of the original sample x′0. The predicted sample xt′ is then calculated using the same posterior distribution q(xt−1|x0). Finally, the discriminator evaluates both the fake pairs D(x′t−1, xt, t) and real pairs D(xt−1, xt, t) to provide feedback to the generator. The decoder D is not necessary for training but is used to convert x′0 back to the output image. We describe the sampling process in Algorithm 1.

4.2. Autoencoder
In the context of latent space representation learning, recent studies, particularly diffusion models ( [30], [33], [34]) and variational autoencoders (VAEs, [31, 32]), frequently employ a KL-penalty (Kullback-Leibler divergence, [53, 54]) between the Gaussian distribution and the learned latent within the loss function. This approach encourages the learned latent space to closely approximate a Gaussian dis-

tribution, proving effective when model assumptions rely heavily on Gaussian distributions. However, with models that allow for complex and multimodal distributions, as in this study, we do not use this KL-penalty. Instead, we allow our autoencoder to freely explore latent spaces and prioritize the ability to compress and recover images effectively.
We construct our autoencoder architecture based on VQGAN [35], distinguished by the integration of a quantization layer within the decoder. To ensure adherence to the image manifold and promote local realism in reconstructions, we employ a training regimen that encompasses both perceptual loss [36] and a patch-based adversarial loss [37, 38], similar to VQGAN. This approach effectively circumvents the potential for blurriness that can arise when training relies exclusively on pixel-space losses such as L2 or L1 objectives. Furthermore, motivated by investigations in [30] that have demonstrated the superiority of two-dimensional latent variables over traditional one-dimensional counterparts in the domains of image compression and reconstruction, we elected to utilize a two-dimensional latent variable as both the output of our encoder and the input to the subsequent diffusion process.
4.3. Loss Functions

### 4.3.1 Adversarial loss

The adversarial loss for the discriminator and the generator are defined as follows.

LDadv = − log(D(xt−1, xt, t)) + log(D(x′t−1, xt, t)) (5)

LGadv = − log(D(xt′−1, xt, t))

(6)

### 4.3.2 Reconstruction loss and Weighted Learning

In WDDGAN [29], in addition to the adversarial loss, a reconstruction loss between the generated sample and its ground truth is also employed during the training of the generator. The generator’s overall objective function is mathematically formulated as a linear combination of adversarial loss and reconstruction loss, weighted by a fixed hyperparameter. It is expressed as follows:

LrGec = ||x0 − x0′ ||

(7)

LG = LDadv + λLGrec

(8)

As investigated in [29], using reconstruction loss helps
WDDGAN improve image fidelity. This enhancement can
be attributed to the fact that when only adversarial loss is used, the generator learns to produce x′0 that is similar to the reference input x0 indirectly, through feedback from the discriminator. However, reconstruction loss provides the gen-erator with direct feedback through the similarity between

x0 and x0′ , calculated using L1 loss. Therefore, employing reconstruction loss in conjunction with adversarial loss facilitates the training of the generator easier and achieve better convergence. There is also evidence in [29] that WDDGAN converges faster than DDGAN. However, we postulate that simply employing a linear combination of the two loss functions, as presented in Eq. 8, to construct the overall loss function proves ineffective and potentially reduces the diversity of generated images. This hypothesis stems from two primary considerations. Firstly, at a certain training stage, the generator acquires the ability to produce data closely resembling the input data solely through the guidance of the discriminator’s feedback, effectively negating the necessity of reconstruction loss. Secondly, reconstruction loss may cause the generator to tend to generate data that is identical to the training data for any given input noise, thereby restricting its capacity for creative exploration and diverse generation.
In this study, we also apply reconstruction loss. However, instead of using a simple linear combination, we propose a method called Weighted Learning to combine the overall loss function of the generator, which is detailed as follows:

struction loss is reduced, giving priority to adversarial loss.

This adjustment is expected to help increase the diversity of

generated images. Finally, as training nears completion, the

importance of reconstruction loss is gradually reduced until

it approaches zero, to avoid excessive changes in the overall

training objective and enhance training stability.

Before starting with Weighted Learning, we also tried removing the reconstruction function after training the model with both loss functions to a certain extent. However, suddenly changing the training objective caused the model to become unstable and difficult to converge again. The experiments to verify the effectiveness of Weighted Learning are presented in Section 5.

For comparison, we use FID and Recall data from previously published papers. To ensure that the FID and Recall results remain consistent with those in the original papers, we adopt the code and experimental environment from the published code of the previous studies mentioned above.

Figure 2. An example of Weighted Learning

## Experiments

We first present a detailed description of the experimental settings, dataset, and evaluation metrics used in Section 5.1. Next, we present experimental results that verify the effectiveness of the proposed LDDGAN and compare these results with previous studies in Section 5.2. Finally, we evaluate the effectiveness of Weighted Learning and the impact of the learned latent space by the Autoencoder in Section 5.3.
5.1. Experimental setup

### 5.1.1 Datasets

To save computational costs, we use CIFAR-10 32 × 32 as the main dataset for qualitative and quantitative comparisons with previous studies, as well as evaluating the effectiveness of each component added to LDDGAN. To further visualize the effectiveness of the model, we use LSUN Church 256 × 256 [40] and CELEBA-HQ 256 × 256 [39] datasets to assess performance through high-resolution image generation tasks.

## Evaluation

metrics
When evaluating our model, we consider three key factors: inference time, sample fidelity, and sample diversity. To assess inference time, we measure the number of function evaluations (NFE) and the average time taken to generate a batch size of 100 across 300 trials. We use the widely recognized Fre´chet Inception Distance (FID, by Heusel et al. in [41]) metric for sample fidelity. To measure sample diversity, we rely on the improved recall score developed by Kynka¨a¨nniemi et al. in [42], which is an enhanced version of the original one proposed by Sajjadi et al. in [43].

### 5.1.3 Autoencoder

As described in Section 4.2, we build our autoencoder based on VQGAN [35], distinguished by the integration of a quantization layer within the decoder. The autoencoder is trained using perceptual loss [36] and patch-based adversarial loss [37, 38] to maintain adherence to the image manifold and promote local realism in the reconstructions. We aim to compress data as much as possible (using a larger scale factor f ), while still ensuring image quality upon decoding. Table 1 lists the autoencoders that were successfully trained for each dataset. All models were trained until convergence, defined as the point where there was no further substantial improvement in FID.

Table 1. Successfully trained autoencoders are used for each dataset. The FID is calculated between the reconstructed images after compression and the original images from the validation set. The output size of these autoencoders will serve as the input size for both the discriminator and the generator.

### 5.1.4 Implementation details

Our implementation is based on DDGAN [28], and we adhered to the same training configurations as those used in DDGAN for our experiments. In constructing our GAN generator, we align with DDGAN’s architectural choice by employing the U-Net-structured NCSN++ framework as presented in Song et al. [44]. To effectively model the denoising distribution within a complex and multimodal context, we leverage latent variable z to exert control over normalization layers. To achieve this, we strategically substitute all group normalization layers (Wu and He [46]) within the generator with adaptive group normalization layers. This technique involves utilizing a straightforward multi-layer fully-connected network to accurately predict the shift and scale parameters within group normalization directly from z. The network’s input consists of by the conditioning element xt, and time embedding is meticulously employed to ensure conditioning on t.
Thanks to the efficient compression of input data through autoencoders, our models require fewer GPU resources

### Table 2
*Model specifications of DDGAN [28], WDDGAN [29] and our approach including a number of parameters (M), FLOPs (GB), and memory usage (GB) on a single GPU for one sample. (*) including the decoder.*

<table>
  <thead>
    <tr>
      <th></th>
      <th>CIFAR-10 (32)<br>CELEBA-HQ (256)</th>
      <th>48.43M<br>39.73M</th>
      <th>7.05G<br>70.82G</th>
      <th>0.31G<br>3.21G</th>
      <th>33.37M<br>31.48M</th>
      <th>1.67G<br>28.54G</th>
      <th>0.16G<br>1.07G</th>
      <th>41.97M<br>45.39M</th>
      <th>1.72G<br>7.15G</th>
      <th>0.18G<br>0.27G</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td></td>
      <td>LSUN(256)</td>
      <td>39.73M</td>
      <td>70.82G</td>
      <td>3.21G</td>
      <td>31.48M</td>
      <td>28.54G</td>
      <td>1.07G</td>
      <td>40.92M</td>
      <td>9.68G</td>
      <td>0.25G</td>
    </tr>
  </tbody>
</table>

### Table 3
*Results on CIFAR-10. (*) including reference time of the decoder. Among diffusion models, our method attains a state-ofthe-art speed while preserving comparable image fidelity.*

<table>
  <thead>
    <tr>
      <th>5.2. Experimental results</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td></td>
      <td>Figure 3. Sample quality vs sampling time trade-off.</td>
      <td>Model<br>Ours<br>WDGAN [29]<br>DDGAN [28]<br>DDP [47]<br>NCSN [44]<br>Adversarial DSM [48]<br>Likelihood SDE [49]<br>Probability Flow (VP) [50]<br>LSGM [51]<br>Score SDE (VE) [45]<br>Score SDE (VP) [45]<br>DDIM [52]<br>FastDDPM [55]<br>Recovery EBM [56]<br>DDPM Distillation [57]<br>SNGAN+DGflow [58]<br>AutoGAN [59]<br>Style<br>GAN<br>2 w/o ADA [60]<br>Style<br>GAN<br>2 w/ ADA [60]<br>Style<br>GAN<br>2 w/ Diffaug [61]</td>
      <td>FID↓<br>2.98<br>4.01<br>3.75<br>3.21<br>25.3<br>6.10<br>2.87<br>3.08<br>2.10<br>2.20<br>2.41<br>4.67<br>3.41<br>9.58<br>9.36<br>9.62<br>12.4<br>8.32<br>2.92<br>5.79</td>
      <td>Recall↑<br>0.58<br>0.55<br>0.57<br>0.57<br>-<br>-<br>-<br>0.57<br>0.61<br>0.59<br>0.59<br>0.53<br>0.56<br>-<br>0.51<br>0.48<br>0.46<br>0.41<br>0.49<br>0.42</td>
      <td>NFE↓<br>4<br>4<br>4<br>1000<br>1000<br>1000<br>1000<br>140<br>147<br>2000<br>2000<br>50<br>50<br>180<br>1<br>25<br>1<br>1<br>1<br>1</td>
      <td>Time(s)↓<br>0.08 (*)<br>0.08<br>0.21<br>80.5<br>107.9<br>-<br>-<br>50.9<br>44.5<br>423.2<br>421.5<br>4.01<br>4.01<br>-<br>-<br>1.98<br>-<br>0.04<br>0.04<br>0.04</td>
    </tr>
    <tr>
      <td>5.2.1</td>
      <td>Overcoming the Generative Learning Trilemma<br>with LDDGAN</td>
      <td>Glow [62]<br>Pixel<br>CNN [63]<br>NVAE [64]<br>VAEBM [65]</td>
      <td>48.9<br>65.9<br>23.5<br>12.2</td>
      <td>-<br>-<br>0.53</td>
      <td>1<br>1024<br>0.51<br>16</td>
      <td>-<br>-<br>0.36<br>8.79</td>
    </tr>
  </tbody>
</table>

### Table 4
*Result on CELEBA-HQ. (*) including reference time of the decoder.*

<table>
  <thead>
    <tr>
      <th>than DDPM.</th>
      <th>In particular,compared to its predecessors,</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
    <tr>
      <th>DDGAN and WDDGAN, our model outperforms on all</th>
      <th></th>
      <th>the decoder.</th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr><td colspan="6"><strong>metrics considered.</strong></td></tr>
    <tr>
      <td>We plot</td>
      <td>the FID score against sampling time of various</td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
    </tr>
    <tr>
      <td></td>
      <td></td>
      <td>Model</td>
      <td>FID↓</td>
      <td>Recall↑</td>
      <td>Time(s)↓</td>
    </tr>
    <tr>
      <td>models in Figure 3 to better benchmark our method. The</td>
      <td></td>
      <td>Ours</td>
      <td>4.67</td>
      <td>0.42</td>
      <td>1.02 (*)</td>
    </tr>
    <tr>
      <td>figure clearly highlights the advantage of our model over</td>
      <td></td>
      <td>WDGAN [29]</td>
      <td>5.06</td>
      <td>0.40</td>
      <td>1.54</td>
    </tr>
    <tr>
      <td>existing diffusion models. When comparing our model with</td>
      <td></td>
      <td>DDGAN [28]</td>
      <td>5.25</td>
      <td>0.41</td>
      <td>3.42</td>
    </tr>
    <tr>
      <td>GANs, only Style<br>GAN<br>2 [60] with adaptive data augmenta-tion has slightly better sample quality than our model. How-ever, Table 3 shows that sample diversity is still their weak-</td>
      <td></td>
      <td>DDPM [47]<br>Image<br>BART [66]<br>PGGAN [39]</td>
      <td>7.89<br>7.32<br>6.42</td>
      <td>-<br>-<br>-</td>
      <td>-<br>-<br>-</td>
    </tr>
    <tr>
      <td>ness, as their</td>
      <td>recall scores are below 0.5.Figure 4 shows</td>
      <td>Style<br>GAN [60]</td>
      <td>4.21</td>
      <td>-</td>
      <td>-</td>
    </tr>
    <tr>
      <td>qualitative samples of CIFAR-10.</td>
      <td></td>
      <td>Style<br>GAN<br>2 [61]</td>
      <td>3.86</td>
      <td>0.36</td>
      <td>-</td>
    </tr>
  </tbody>
</table>

Table 5. Result on LSUN Church. (*) including reference time of the decoder.

impact of reconstruction loss on the training results of the model as well as the contribution of Weighted Learning.
We trained our model using three different overall loss functions for the generator: (i) adversarial loss alone, (ii) a simple linear combination of adversarial loss and reconstruction loss similar to Eq. 8, and (iii) a combination of adversarial loss and reconstruction loss using Weighted Learning. Experimental results are summarized in Table 6.

Dataset CIFAR10
CELEBA HQ

Model AdvLoss AdvLoss + RecLoss AdvLoss + RecLoss + WL AdvLoss AdvLoss + RecLoss AdvLoss + RecLoss + WL

FID↓ 3.15 3.09 3.03 5.27 5.23 5.21

Recall↑ 0.58 0.56 0.58 0.39 0.36 0.40

Table 6. Contribution of reconstruction loss and Weighted Learning. ”AdvLoss” denotes adversarial loss, ”RecLoss” denotes reconstruction loss, ”WL” denotes Weighted Learning.

As shown in Table 6, employing reconstruction loss yields better FID scores than relying solely on adversarial loss for both datasets. This improvement arises because reconstruction loss provides the generator with additional direct feedback regarding the disparity between the input training data and the data generated by the model, facilitating the rapid generation of data with superior image qual-

(a) LSUN Church

(b) CELEBA-HQ

Figure 5. Qualitative results on LSUN Church and CELEBA-HQ.

ity. However, reconstruction loss can also be interpreted as necessitating the generator to produce data identical to the input data using random noise. Consequently, after a certain amount of training, the generator tends to generate similar data with different input random noise, thereby reducing sample diversity. The results in Table 6 illustrate this reduction in recall compared to scenarios without the use of reconstruction loss.
Weighted Learning is implemented to capitalize on reconstruction loss in the early stages, gradually diminishing its priority to emphasize adversarial loss and enhance sample diversity. Towards the end of training, the rate at which reconstruction loss diminishes is reduced to ensure training stability. This strategic approach allows us to leverage reconstruction loss effectively, improving FID scores while ensuring sample diversity. As shown in Table 6, the utilization of Weighted Learning helps us achieve better results for both FID and Recall.
5.3.2 Affect of learned latent space by Autoencoder
As outlined in Section 4.2, introducing a KL-penalty towards a Gaussian distribution in the learned latent space proves effective for models relying on Gaussian-dependent structures ( [30], [31, 32], [33]). Nevertheless, such a penalty is deemed unnecessary and potentially detrimental for our model, which operates with complex and multimodal distributions.
To verify this hypothesis, we trained autoencoders under two settings: (i) using only perceptual loss and a patchbased adversarial loss, as presented in Section 4.2, and (ii) adding a KL-penalty between the learned latent and a Gaussian distribution to the aforementioned loss functions. We selected autoencoders with reconstruction FID scores close to each other to objectively compare their effectiveness through FID and Recall of the main model.
The results in Table 7 show that when autoencoders are allowed to freely search for the appropriate latent space, they converge significantly faster, requiring fewer epochs to reach a reconstruction FID comparable to those using a KL-penalty. When comparing the results of FID and Re-

call of the main model, the ability to freely search for the appropriate latent space, instead of relying on latent spaces close to a Gaussian distribution, significantly improves the results in most cases. Notably, in the case of CelebA-HQ, even though using an autoencoder with a worse reconstruction FID than one using a KL-penalty, the main model still achieves better FID and Recall scores. FID is also significantly improved in the cases of CIFAR-10 and LSUN. This result validates our hypothesis.
5.3.3 The role of the autoencoder in achieving high performance
One evident observation from the experimental results is the strong dependence of our model on pre-trained autoencoders. A proficient autoencoder plays a crucial role in compressing images to their smallest form, thereby significantly reducing computational costs and enhancing inference speed. Moreover, this compression facilitates the training of the generator by ensuring that essential features are effectively and comprehensively extracted by the encoder. The LSUN case in this study exemplifies this pattern, as demonstrated in Tables 2 and 5. Notably, well-designed autoencoders like this can also be repurposed for training future models for other tasks, such as text-to-image or superresolution.
Conversely, our model fails to achieve optimal performance without the presence of a proficient autoencoder, as evidenced by the results on CIFAR-10 in Table 3. Despite only compressing data four times, which is not significantly different from WDDGAN [29], our model, by leveraging latent space features, attains superior FID and Recall scores. However, the inference speed is almost equivalent to that of WDDGAN. Additionally, in this scenario, as shown in Table 2, the total number of parameters and FLOPs has increased compared to WDDGAN due to the inclusion of the autoencoder.

### Table 7
*Comparison results between using and not using a KL-penalty between the learned latent and a standard normal distribution when training autoencoders.*

<table>
  <thead>
    <tr>
      <th>CIFAR-101.33 (525ep)1.32 (300ep)</th>
      <th>3.15</th>
      <th>3.030.580.58</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>CELEBA-HQ0.56 (625ep)0.58 (450ep)</td>
      <td>5.88</td>
      <td>5.830.400.37</td>
    </tr>
    <tr>
      <td>LSUN Church<br>1.16 (675ep)1.14 (525ep)</td>
      <td>4.89</td>
      <td>4.670.420.41</td>
    </tr>
  </tbody>
</table>

LDDGAN’s Recall ↑

KL penalty 0.58 0.37 0.41

w/o KL penalty 0.58 0.40 0.42

Table 7. Comparison results between using and not using a KL-penalty between the learned latent and a standard normal distribution when training autoencoders. The autoencoders are selected to have nearly identical FID reconstruction scores to ensure the objectivity of the comparison of the results of the main model. The numbers in (*) indicate the number of epochs required to train the autoencoder.

## Conclusion

In this paper, we introduce a new diffusion model called LDDGAN. The core concept of our approach involves transitioning from the complex, high-dimensional pixel space to an efficient, low-dimensional latent space using a pretrained autoencoder. Subsequently, the GAN mechanism facilitates the diffusion process, resulting in a notable reduction in computational costs, an acceleration in inference speed, and improvements in the quality and diversity of generated images. To further enhance the quality and diversity of images, we eliminate the dependence of the latent space learned by autoencoders on Gaussian distributions and propose Weighted Learning to effectively combine reconstruction loss and adversarial loss. Our model achieves state-ofthe-art inference speed for a diffusion model. In comparison to GANs, we attain comparable image generation quality and inference speed, along with higher diversity. Furthermore, when compared to two predecessors, DDGAN [28] and WDDGAN [29], our model significantly outperforms them across the majority of comparison metrics. With these initial results, we aim to foster future studies on real-time and high-fidelity diffusion models.

## References

[1] P. Dhariwal and A. Nichol, ”Diffusion models beat gans on image synthesis”, Advances in Neural Information Processing Systems, 34:8780–8794, 2021. 1
[2] C. Saharia, W. Chan, S. Saxena, L. Li, J. Whang, E. Denton, S. Ghasemipour, B. K. Ayan, S. Mahdavi, R. Lopes, ”Photorealistic text-to-image diffusion models with deep language understanding”, arXiv preprint, arXiv:2205.11487, 2022. 1
[3] C. Huang, J. H. Lim, and A. Courville, ”A variational perspective on diffusion-based generative models and score matching”, Advances in Neural Information Processing Systems, 34:22863–22876, 2021. 1
[4] D. Kingma, T. Salimans, B. Poole, and J. Ho, ”Variational diffusion models”. Advances in neural information processing systems, 34:21696–21707, 2021. 1, 2

[5] A. Ramesh, P. Dhariwal, A. Nichol, C. Chu, and M. Chen, ”Hierarchical text-conditional image generation with clip latents”, ArXiv preprint, arXiv:2204.06125, 2022. 1
[6] J. Choi, S. Kim, Y. Jeong, Y. Gwon, and S. Yoon, ”Ilvr: Conditioning method for denoising diffusion probabilistic models”, ArXiv preprint, arXiv:2108.02938, 2021. 1
[7] C. Meng, Y. Song, J. Song, J. Wu, J. Zhu, and S. Ermon, ”Sdedit: Image synthesis and editing with stochastic differential equations”, ArXiv preprint, arXiv:2108.01073, 2021. 1
[8] J. Ho, W. Chan, C. Saharia, J. Whang, R. Gao, A. Gritsenko, D. P. Kingma, B. Poole, M. Norouzi, D. J. Fleet, ”Imagen video: High definition video generation with diffusion models”, ArXiv preprint, arXiv:2210.02303, 2022. 1
[9] M. Zhao, F. Bao, C. Li, and J. Zhu. Egsde, ”Unpaired image-to-image translation via energy-guided stochastic differential equations”, Computer Vision and Pattern Recognition, 2022. 1
[10] J. Ho, T. Salimans, A. Gritsenko, W. Chan, M. Norouzi, and D. J. Fleet, ”Video diffusion models”, Computer Vision and Pattern Recognition, 2022 1
[11] B. Poole, A. Jain, J. T. Barron, and B. Mildenhall, ”Dreamfusion: Text-to-3d using 2d diffusion”, Computer Vision and Pattern Recognition, 2022. 1
[12] I. J. Goodfellow, J. P.Abadie, M. Mirza, B. Xu, D. W. Farley, S. Ozair, A. C. Courville, and Y. Bengio, ”Generative adversarial networks”, CoRR, 2014. 2
[13] D. P. Kingma and M. Welling, ”Auto-Encoding Variational Bayes”, In 2nd International Conference on Learning Representations, ICLR, 2014. 2
[14] L. Dinh, D. Krueger, and Y. Bengio, ”Nice: Non-linear independent components estimation”, arXiv:1410.8516, 2015. 2

[15] L. Dinh, J. Sohl-Dickstein, and S. Bengio, ”Density estimation using real NVP”, In 5th International Conference on Learning Representations, ICLR 2017, Toulon, France, April 24-26, 2017. 2
[16] M. Arjovsky, S. Chintala, and L. Bottou, ”Wasserstein gan”, arXiv:1701.07875, 2017. 2
[17] A. Brock, J. Donahue, and K. Simonyan, ”Large scale GAN training for high fidelity natural image synthesis”, In Int. Conf. Learn. Represent., 2019. 2
[18] I. Gulrajani, F. Ahmed, M. Arjovsky, V. Dumoulin, and A. Courville, ”Improved training of wasserstein gans”, arXiv:1704.00028, 2017. 2
[19] L. M. Mescheder, ”On the convergence properties of GAN training”, CoRR, arXiv:1801.04406, 2018. 2
[20] L. Metz, B. Poole, D. Pfau, and J. SohlDickstein, ”Unrolled generative adversarial networks”, In 5th International Conference on Learning Representations, ICLR 2017. 2
[21] P. Dhariwal and A. Nichol, ”Diffusion models beat gans on image synthesis”, CoRR, arXiv:2105.05233, 2021. 2
[22] R. San-Roman, E. Nachmani, and L. Wolf, ”Noise estimation for generative diffusion models”, arXiv preprint arXiv:2104.02600, 2021. 2
[23] A. Jolicoeur-Martineau, K. Li, R. Piche-Taillefer, T. Kachman, and I. Mitliagkas, ”Gotta go fast when generating data with score-based models”, arXiv preprint arXiv:2105.14080, 2021a. 2
[24] R. Abdal, Y. Qin, P. Wonka, ”Image2StyleGAN: How to Embed Images Into the StyleGAN Latent Space”, Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV), pp. 4432-4441, 2019.
[25] J. Sohl-Dickstein, E. Weiss, N. Maheswaranathan, and S. Ganguli, ”Deep unsupervised learning using nonequilibrium thermodynamics”, In International Conference on Machine Learning, 2015. 3
[26] W Feller, ”On the theory of stochastic processes, with particular reference to applications”, In Proceedings of the [First] Berkeley Symposium on Mathematical Statistics and Probability, pp. 403–432. University of California Press, 1949. 3
[27] F. Bao, C. Li, J. Zhu, and B. Zhang, ”Analyticdpm: an analytic estimate of the optimal reverse variance in diffusion probabilistic models”, International Conference on Learning Representations 2022, 2022. 3

[28] Z. Xiao, K. Keris, A. Vahdat, “Tackling The Generative Learning Trilemma With Denoising Diffusion Gans”, International Conference on Learning Representations, 2022. 1, 3, 6, 7, 8, 10
[29] H. Phung, Q. Dao, A. Tran:” Wavelet Diffusion Models are fast and scalable Image Generators”, International Conference on Learning Representations, 2023. 1, 3, 5, 7, 8, 9, 10
[30] R. Rombach, A. Blattmann, D. Lorenz, P. Esser, B. Ommer, ”High-Resolution Image Synthesis with Latent Diffusion Models”, arXiv:2112.10752v2, 2022. 1, 2, 3, 4, 5, 9
[31] D. P. Kingma and M. Welling, ”Auto-Encoding Variational Bayes”, In 2nd International Conference on Learning Representations, ICLR, 2014. 4, 9
[32] D. Jimenez Rezende, S. Mohamed, and D. Wierstra, ”Stochastic backpropagation and approximate inference in deep generative models”, In Proceedings of the 31st International Conference on International Conference on Machine Learning, ICML, 2014. 4, 9
[33] O. Avarahami, O. Fried, D. Lischinski, ”Blended Latent Diffusion”, ACM Transactions on Graphics, Vol. 42, No. 4, Article 149, 2022. 4, 9
[34] D. Podell, Z. English, K. Lacey, A. Blattmann, T. Dockhorn, J. Mu¨ller, J. Penna, R. Rombach, ”SDXL: Improving Latent Diffusion Models for HighResolution Image Synthesis”, arXiv:2307.01952, 2023. 4
[35] P. Esser, R. Rombach, and B. Ommer, ”Taming transformers for high-resolution image synthesis”, CoRR, abs/2012.09841, 2020. 5, 6, 8
[36] R. Zhang, P. Isola, A. A. Efros, E. Shechtman, and O. Wang, ”The unreasonable effectiveness of deep features as a perceptual metric”, In Proceedings of the IEEE Conference on Computer Vision and Pattern Recog- nition (CVPR), June 2018. 5, 6
[37] J. Yu, X. Li, J. Yu Koh, H. Zhang, R. Pang, J. Qin, A. Ku, Y. Xu, J. Baldridge, and Y. Wu, ” Vectorquantized image modeling with improved vqgan”, 2021. 5, 6
[38] A. Dosovitskiy and T. Brox, ”Generating images with perceptual similarity metrics based on deep networks”, In Daniel D. Lee, Masashi Sugiyama, Ulrike von Luxburg, Isabelle Guyon, and Roman Garnett, editors, Adv. Neural Inform. Process. Syst., pages 658–666, 2016. 5, 6

[39] T. Karras, T. Aila, S. Laine, and J. Lehtinen, ”Progressive growing of GANs for im- proved quality, stability, and variation”, In International Conference on Learning Representations, 2018. 6, 8
[40] F. Yu, A. Seff, Y. Zhang, S. Song, T. Funkhouser, and J. Xiao, ”Lsun: Construction of a large-scale image dataset using deep learning with humans in the loop”, arXiv preprint arXiv:1506.03365, 2015. 6
[41] M. Heusel, H. Ramsauer, T. Unterthiner, B. Nessler, and S. Hochreiter, ”Gans trained by a two time-scale update rule converge to a local nash equilibrium”, Advances in neural information processing systems, 2017. 6
[42] T. Kynkaanniemi, T. Karras, S. Laine, J. Lehtinen, and T. Aila, ”Improved precision and recall metric for assessing generative models”, arXiv preprint arXiv:1904.06991, 2019. 6
[43] M. S. Sajjadi, O. Bachem, M. Lucic, O. Bousquet, and S. Gelly, ”Assessing generative models via precision and recall”, arXiv preprint arXiv:1806.00035, 2018. 6
[44] Y. Song and S. Ermon, ”Generative modeling by estimating gradients of the data distribution”, In Advances in neural information processing systems, 2019. 6, 7, 8, 13
[45] Y. Song, J. Sohl-Dickstein, D. P. Kingma, A. Kumar, S. Ermon, and B. Poole, ”Score-based generative modeling through stochastic differential equations”, In International Conference on Learning Representations, 2021c. 2, 3, 7, 8
[46] Y. Wu and K. He, ”Group normalization”, In Proceedings of the European conference on computer vision, 2018. 6
[47] J. Song, C. Meng, and S. Ermon, ”Denoising diffusion implicit models”, In International Conference on Learning Representations, 2021a. 2, 3, 7, 8
[48] A. Jolicoeur-Martineau, R. P. Taillefer, I. Mitliagkas, and R. Tachet des Combes, ”Adversarial score matching and improved sampling for image generation”, In Inter- national Conference on Learning Representations, 2021b. 7
[49] Y. Song, C. Durkan, I. Murray, and S. Ermon, ”Maximum likelihood training of score-based diffusion models”, arXiv preprint arXiv:2101.09258, 2021b. 1, 3, 7

[50] Y. Song, J. Sohl-Dickstein, D. P Kingma, A. Kumar, S. Ermon, and B. Poole, ”Score-based generative modeling through stochastic differential equations”, In International Conference on Learning Representations, 2021c. 7
[51] A. Vahdat, K. Kreis, and J. Kautz, ”Score-based generative modeling in latent space”, In Advances in neural information processing systems, 2021. 7
[52] J. Song, C. Meng, and S. Ermon, ”Denoising diffusion implicit models”, In International Conference on Learning Representations, 2021a. 7
[53] T.M. Cover and J. A. Thomas, ”Elements of information theory”, John Wiley & Sons, New York, 1991. 4
[54] J. Shlens, ”Notes on Kullback-Leibler Divergence and Likelihood”, arXiv:1404.2000, 2014 4
[55] Z. Kong and W. Ping, ”On fast sampling of diffusion probabilistic models”, arXiv preprint, arXiv:2106.00132, 2021. 2, 7
[56] R. Gao, Y. Song, B. Poole, Y. Nian Wu, and D. P. Kingma, ”Learning energy-based models by diffusion recovery likelihood”, In International Conference on Learning Representations, 2021. 7
[57] E. Luhman and T. Luhman, ”Knowledge distillation in iterative generative models for improved sampling speed”, arXiv preprint, arXiv:2101.02388, 2021. 2, 7
[58] T. Miyato, T. Kataoka, M. Koyama, and Y. Yoshida, ”Spectral normalization for generative adversarial networks”, arXiv preprint, arXiv:1802.05957, 2018. 7
[59] X. Gong, S. Chang, Y. Jiang, and Z. Wang, ”Autogan: Neural architecture search for generative adversarial networks”, In Proceedings of the IEEE conference on computer vision and pattern recognition, 2019. 7
[60] T. Karras, M. Aittala, J. Hellsten, S. Laine, J. Lehtinen, and T. Aila. ”Training generative adversarial networks with limited data”, In Advances in neural information processing systems, 2020a. 1, 7, 8
[61] T. Karras, S. Laine, M. Aittala, J. Hellsten, J. Lehtinen, and T. Aila, ”Analyzing and improving the image quality of stylegan”, In Proceedings of the IEEE conference on computer vision and pattern recognition, 2020b. 7, 8
[62] D. P. Kingma and P. Dhariwal, ”Glow: Generative flow with invertible 1x1 convolutions”, In Advances in neural information processing systems, 2018. 7

### Table 8
*Network configurations for the generator.*

<table>
  <thead>
    <tr>
      <th>[63] A.</th>
      <th>van<br>Kavukcuoglu, ”Pixel<br>ternational Conference on Machine Learning, 2016b.</th>
      <th>den</th>
      <th>Oord,</th>
      <th>N.<br>recurrent neural networks”,</th>
      <th>Kalchbrenner,</th>
      <th>and</th>
      <th>K.<br>In-</th>
      <th># of ResNet blocks per scale<br>Base channels<br>Channel multiplier per scale</th>
      <th>CIFAR<br>10<br>2<br>128<br>(1,2,2)</th>
      <th>CELEBA-HQ<br>2<br>128<br>(1,2,2,2)</th>
      <th>LSUN<br>2<br>128<br>(1,2,2,2)</th>
    </tr>
    <tr>
      <th>7</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th>Attention resolutions<br>Latent Dimension<br># of latent mapping layers</th>
      <th>None<br>25<br>4</th>
      <th>16<br>25<br>4</th>
      <th>16<br>25<br>4</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>[64] A. Vahdat and J. Kautz, ”NVAE: A deep hierarchical</td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td>Latent embedding dimension</td>
      <td>256</td>
      <td>256</td>
      <td>256</td>
    </tr>
  </tbody>
</table>

### Table 9
*Network structures for the discriminator. The number on the right is the number of channels of Conv in each residual block.*

<table>
  <thead>
    <tr>
      <th></th>
      <th></th>
      <th>Attention resolutions<br>Latent Dimension<br># of latent mapping layers</th>
      <th>None<br>25<br>4</th>
      <th>25<br>4</th>
      <th>25<br>4</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>[64] A. Vahdat and J. Kautz, ”NVAE: A deep hierarchical</td>
      <td></td>
      <td>Latent embedding dimension</td>
      <td>256</td>
      <td>256</td>
      <td>256</td>
    </tr>
  </tbody>
</table>

### Table 10
*Training hyper-parameters.*

<table>
  <thead>
    <tr>
      <th></th>
      <th>Models”, Computer Vision and Pattern Recognition,<br>2023. 13</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th>LSUN requires 2.1 days on 2 GPUs.</th>
      <th>coders. Regarding training times, CIFAR<br>10 requires 1 day<br>on 1 GPU, CELEBA-HQ requires 1.5 days on 2 GPUs, and</th>
      <th></th>
      <th></th>
    </tr>
    <tr>
      <th>[69] T.</th>
      <th>Yin, M.<br>F. Durand, W.</th>
      <th>Gharbi,<br>T.</th>
      <th>R.<br>Freeman,</th>
      <th>Zhang,<br>T.</th>
      <th>E.<br>Park,</th>
      <th>Shechtman,<br>”One-step</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td></td>
      <td>Diffusion with Distribution Matching Distillation”,<br>arXiv:2311.18828, 2023. 2</td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td>Learning rate of G<br>Learning rate of D</td>
      <td>CIFAR<br>10<br>1.6e-4<br>1.25e-4</td>
      <td>CELEBA-HQ<br>2e-4<br>1e-4</td>
      <td>LSUN<br>2e-4<br>1e-4</td>
    </tr>
    <tr>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td>EMA</td>
      <td>0.9999</td>
      <td>0.999</td>
      <td>0.999</td>
    </tr>
    <tr>
      <td>[70] A. Sauer, D. Lorenz, A. Blattmann, R. Rombach, ”Ad-2023.</td>
      <td>versarial Diffusion Distillation”,</td>
      <td></td>
      <td></td>
      <td></td>
      <td>arXiv:2311.17042,</td>
      <td></td>
      <td>Batch size<br>Lazy regularization<br>Numner of epochs<br>Number of timesteps</td>
      <td>256<br>15<br>1700<br>4</td>
      <td>128<br>10<br>400<br>2</td>
      <td>128<br>10<br>400<br>4</td>
    </tr>
  </tbody>
</table>
4 2

Table 10. Training hyper-parameters.

C. Choosing backbone for latent space
When transitioning from pixel space to latent space, we carefully consider a suitable backbone for the generator in this space. We particularly pay attention to Vision Transformers (ViTs) models due to their ability to extract longrange relationships and high compatibility with latent space. Recently, a ViT-based Unet introduced by Xiao et al. in [68] has demonstrated the potential to replace the widely used

CNN-based Unet in diffusion models. To compare the effectiveness of ViT and CNN backbones for tasks in this study, we construct another generator based on this model. Except for the generator’s architecture, we maintain the core model as depicted in Figure 1. Timestep t and xt are input to the generator as a token after passing through embedding layers. We introduce adaptive group normalization layers into the transformer blocks of the ViT-based Unet and control them with the latent variable z, similar to the CNNbased Unet described in Section 5. This helps the generator model denoising distributions within a complex and multimodal context. Other settings of the ViT-based Unet are kept consistent with [68]. We conduct experiments with three different scales of the model: Tiny, Mid, and Large, and subsequently compare the results with the CNN-based Unet.

### Table 11
*Comparison of computational cost between CNN-based and ViT-based UNet.*

<table>
  <thead>
    <tr>
      <th>Unet model</th>
      <th>features and distributions more rapidly, espe-</th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr><td colspan="3"><strong>cially as we utilize two-dimensional latent variables, similar</strong></td></tr>
    <tr><td colspan="3"><strong>to the image data that CNNs are designed to process.</strong></td></tr>
    <tr>
      <td>Model</td>
      <td>Param (M) ↓</td>
      <td>MEM (GB) ↓</td>
    </tr>
    <tr>
      <td>CNN based</td>
      <td>41.97</td>
      <td>0.18</td>
    </tr>
    <tr>
      <td>ViT based, Tiny</td>
      <td>28.01</td>
      <td>0.08</td>
    </tr>
    <tr>
      <td>ViT based, Mid</td>
      <td>43.32</td>
      <td>0.21</td>
    </tr>
    <tr>
      <td>ViT based, Large</td>
      <td>56.17</td>
      <td>0.32</td>
    </tr>
  </tbody>
</table>

### Table 12
*Comparisonal results between CNN-based and ViTbased UNet on CIFAR-10.*

<table>
  <thead>
    <tr>
      <th>and ViT-based UNet.<br>Model</th>
      <th>FID↓</th>
      <th>Recall↑</th>
      <th>NFE↓</th>
      <th>Time(s)↓</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>CNN based</td>
      <td>2.98</td>
      <td>0.58</td>
      <td>4</td>
      <td>0.08</td>
    </tr>
    <tr>
      <td>ViT based, Tiny</td>
      <td>4.33</td>
      <td>0.54</td>
      <td>4</td>
      <td>0.06</td>
    </tr>
    <tr>
      <td>ViT based, Mid</td>
      <td>3.21</td>
      <td>0.57</td>
      <td>4</td>
      <td>0.09</td>
    </tr>
    <tr>
      <td>ViT based, Large</td>
      <td>2.97</td>
      <td>0.59</td>
      <td>4</td>
      <td>0.13</td>
    </tr>
  </tbody>
</table>

(c) Ours
Figure 6. Additional qualitative samples and qualitative comparision on CelebA-HQ.

(c) Ours
Figure 7. Additional qualitative samples and qualitative comparision on LSUN Church.

## Figures

*Figure 1. The training process of Latent Denoising Diffusion GAN (LDDGAN) 4.1.*

*Figure 2. An example of Weighted Learning 5.*

*Figure 3. Sample quality vs sampling time trade-off.*

*Figure 4. CIFAR-10 qualitative samples.*

*Figure 5. Qualitative results on LSUN Church and CELEBA-HQ.*

*Figure 6. Additional qualitative samples and qualitative comparision on CelebA-HQ.*

*Figure 7. Additional qualitative samples and qualitative comparision on LSUN Church.*

## Tables (unlocated in body)

### Table 1
*Successfully trained autoencoders are used for each dataset. The FID is calculated between the reconstructed images after compression and the original images from the validation set. The output size of these autoencoders will serve as the input size for both the discriminator and the generator.*

```
For comparison, we use FID and Recall data from previ-
ously published papers. To ensure that the FID and Recall
results remain consistent with those in the original papers,
we adopt the code and experimental environment from the
published code of the previous studies mentioned above.

### 5.1.3 Autoencoder

As described in Section 4.2, we build our autoencoder based
on VQGAN [35], distinguished by the integration of a quan-
tization layer within the decoder. The autoencoder is trained
using perceptual loss [36] and patch-based adversarial loss
[37, 38] to maintain adherence to the image manifold and
promote local realism in the reconstructions. We aim to
compress data as much as possible (using a larger scale fac-
tor f ), while still ensuring image quality upon decoding.
Table 1 lists the autoencoders that were successfully trained
Figure 2. An example of Weighted Learning
for each dataset. All models were trained until convergence,
defined as the point where there was no further substantial
improvement in FID.
5. Experiments
We first present a detailed description of the experimen-
Dataset Scale factor f Ouput size FID
tal settings, dataset, and evaluation metrics used in Sec-
16 × 16 × 4 CIFAR-10 2 1.32
tion 5.1. Next, we present experimental results that verify
64 × 64 × 4 CELEBA-HQ 4 0.58
the effectiveness of the proposed LDDGAN and compare
32 × 32 × 3 LSUN Church 8 1.14
these results with previous studies in Section 5.2. Finally,
we evaluate the effectiveness of Weighted Learning and the Table 1. Successfully trained autoencoders are used for each
impact of the learned latent space by the Autoencoder in dataset. The FID is calculated between the reconstructed images
Section 5.3. after compression and the original images from the validation set.
The output size of these autoencoders will serve as the input size
5.1. Experimental setup for both the discriminator and the generator.

### 5.1.1 Datasets

To save computational costs, we use CIFAR-10 32 × 32

### 5.1.4 Implementation details

as the main dataset for qualitative and quantitative compar-
isons with previous studies, as well as evaluating the ef- Our implementation is based on DDGAN [28], and we ad-
fectiveness of each component added to LDDGAN. To fur- hered to the same training configurations as those used in
ther visualize the effectiveness of the model, we use LSUN DDGAN for our experiments. In constructing our GAN
Church 256 × 256 [40] and CELEBA-HQ 256 × 256 [39] generator, we align with DDGAN’s architectural choice
datasets to assess performance through high-resolution im- by employing the U-Net-structured NCSN++ framework as
age generation tasks. presented in Song et al. [44]. To effectively model the de-
noising distribution within a complex and multimodal con-
text, we leverage latent variable z to exert control over nor-

### 5.1.2 Evaluation metrics

malization layers. To achieve this, we strategically sub-
When evaluating our model, we consider three key factors: stitute all group normalization layers (Wu and He [46])
inference time, sample fidelity, and sample diversity. To within the generator with adaptive group normalization lay-
assess inference time, we measure the number of function ers. This technique involves utilizing a straightforward
evaluations (NFE) and the average time taken to generate multi-layer fully-connected network to accurately predict
a batch size of 100 across 300 trials. We use the widely the shift and scale parameters within group normalization
recognized Fr´echet Inception Distance (FID, by Heusel et directly from z. The network’s input consists of by the con-
al. in [41]) metric for sample fidelity. To measure sample ditioning element xt, and time embedding is meticulously
diversity, we rely on the improved recall score developed employed to ensure conditioning on t.
by Kynk¨a¨anniemi et al. in [42], which is an enhanced ver- Thanks to the efficient compression of input data through
sion of the original one proposed by Sajjadi et al. in [43]. autoencoders, our models require fewer GPU resources
```

### Table 6
*Contribution of reconstruction loss and Weighted Learning. ”AdvLoss” denotes adversarial loss, ”RecLoss” denotes reconstruction loss, ”WL” denotes Weighted Learning.*

<table>
  <thead>
    <tr>
      <th>have made significant progress in addressing the slow sam-</th>
      <th>Model FID↓ Recall↑ Time(s)↓</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>pling weakness of diffusion models. The results in Ta-</td>
      <td>5.21 0.40 Ours 0.55 (*)</td>
    </tr>
    <tr>
      <td>ble 3 demonstrate that our model further improves upon this</td>
      <td>WDGAN [29] 5.94 0.37 0.60</td>
    </tr>
    <tr>
      <td>weakness, achieving state-of-the-art running speed among</td>
      <td>DDGAN [28] 7.64 0.36 1.73</td>
    </tr>
    <tr>
      <td>diffusion models while maintaining competitive sample</td>
      <td>Score SDE [45] 7.23 - -</td>
    </tr>
    <tr>
      <td>quality. While a few variants of diffusion models, such as</td>
      <td>NVAE [64] 29.7 - -</td>
    </tr>
    <tr>
      <td>Score SDE [44] or DDPM [47], achieve better FID scores</td>
      <td>VAEBM [65] 20.4 - -</td>
    </tr>
    <tr>
      <td>than our model, our model achieves a sampling speed that</td>
      <td>PGGAN [39] 8.03 - -</td>
    </tr>
    <tr>
      <td>is 5000 times faster than Score SDE and 1000 times faster</td>
      <td>VQ-GAN [35] 10.2 - -</td>
    </tr>
    <tr>
      <td>than DDPM. In particular, compared to its predecessors,</td>
      <td>Table 4. Result on CELEBA-HQ. (*) including reference time of</td>
    </tr>
    <tr>
      <td>DDGAN and WDDGAN, our model outperforms on all</td>
      <td>the decoder.</td>
    </tr>
    <tr>
      <td>metrics considered.</td>
      <td></td>
    </tr>
    <tr>
      <td>We plot the FID score against sampling time of various</td>
      <td>Model FID↓ Recall↑ Time(s)↓</td>
    </tr>
    <tr>
      <td>models in Figure 3 to better benchmark our method. The</td>
      <td>4.67 0.42 Ours 1.02 (*)</td>
    </tr>
    <tr>
      <td>figure clearly highlights the advantage of our model over</td>
      <td>WDGAN [29] 5.06 0.40 1.54</td>
    </tr>
    <tr>
      <td>existing diffusion models. When comparing our model with</td>
      <td>DDGAN [28] 5.25 0.41 3.42</td>
    </tr>
    <tr>
      <td>GANs, only Style<br>GAN<br>2 [60] with adaptive data augmenta-tion has slightly better sample quality than our model. How-ever, Table 3 shows that sample diversity is still their weak-ness, as their recall scores are below 0.5. Figure 4 shows</td>
      <td>DDPM [47] 7.89 - -<br>Image<br>BART [66] 7.32 - -<br>PGGAN [39] 6.42 - -<br>Style<br>GAN [60] 4.21 - -</td>
    </tr>
    <tr>
      <td>qualitative samples of CIFAR-10.</td>
      <td>Style<br>GAN<br>2 [61] 3.86 0.36 -</td>
    </tr>
    <tr>
      <td>5.2.2 High-resolution image generation</td>
      <td>Table 5. Result on LSUN Church. (*) including reference time of<br>the decoder.</td>
    </tr>
    <tr>
      <td>To further evaluate the effectiveness of our model, we</td>
      <td></td>
    </tr>
    <tr>
      <td>trained it on two high-resolution datasets: LSUN Church</td>
      <td></td>
    </tr>
    <tr>
      <td>and Celeb<br>A-HQ. Table 4 and Table 5 present the results of</td>
      <td>impact of reconstruction loss on the training results of the</td>
    </tr>
    <tr>
      <td>comparisons with previous models. Similar to CIFAR-10,</td>
      <td>model as well as the contribution of Weighted Learning.</td>
    </tr>
    <tr>
      <td>our model outperforms the two predecessors, DDGAN and</td>
      <td>We trained our model using three different overall loss</td>
    </tr>
    <tr>
      <td>WDDGAN, on all three comparison metrics. In particu-</td>
      <td>functions for the generator: (i) adversarial loss alone, (ii)</td>
    </tr>
    <tr>
      <td>lar, for the LSUN dataset, as shown in Table 1, success-</td>
      <td>a simple linear combination of adversarial loss and recon-</td>
    </tr>
    <tr>
      <td>fully compressing the input data by a factor of 8 signifi-</td>
      <td>struction loss similar to Eq. 8, and (iii) a combination of ad-</td>
    </tr>
    <tr>
      <td>cantly reduces the inference time of the model. Our model</td>
      <td>versarial loss and reconstruction loss using Weighted Learn-</td>
    </tr>
    <tr>
      <td>is 1.5 times faster than WDDGAN and 3 times faster than</td>
      <td>ing. Experimental results are summarized in Table 6.</td>
    </tr>
    <tr>
      <td>DDGAN. When compared to other diffusion models such</td>
      <td></td>
    </tr>
    <tr>
      <td>as DDPM or Score SDE, our model achieves comparable</td>
      <td>Dataset Model FID↓ Recall↑</td>
    </tr>
    <tr>
      <td>or better FID results. Compared to traditional GANs such</td>
      <td>AdvLoss 3.15 0.58<br>CIFAR<br>10 AdvLoss + RecLoss 3.09 0.56</td>
    </tr>
    <tr>
      <td>as Style<br>GAN<br>2, our model obtains competitive sample qual-ity while outperforming GANs in terms of sample diversity.</td>
      <td>3.03 0.58 AdvLoss + RecLoss + WL<br>AdvLoss 5.27 0.39</td>
    </tr>
    <tr>
      <td>Figure 5 displays qualitative samples from LSUN Church</td>
      <td>CELEBA HQ AdvLoss + RecLoss 5.23 0.36</td>
    </tr>
    <tr>
      <td>and Celeb<br>A-HQ.</td>
      <td>5.21 0.40 AdvLoss + RecLoss + WL</td>
    </tr>
    <tr>
      <td>5.3. Ablation studies</td>
      <td>Table 6. Contribution of reconstruction loss and Weighted Learn-<br>ing. ”AdvLoss” denotes adversarial loss, ”RecLoss” denotes re-</td>
    </tr>
    <tr>
      <td>5.3.1 Contribution of reconstruction loss and</td>
      <td>construction loss, ”WL” denotes Weighted Learning.</td>
    </tr>
    <tr>
      <td>Weighted Learning</td>
      <td></td>
    </tr>
    <tr>
      <td>As described in Section 4.3.2, using reconstruction loss</td>
      <td>As shown in Table 6, employing reconstruction loss</td>
    </tr>
    <tr>
      <td>helps to achieve better FID scores but may reduce sample</td>
      <td>yields better FID scores than relying solely on adversarial</td>
    </tr>
    <tr>
      <td>diversity. To leverage the effectiveness of reconstruction</td>
      <td>loss for both datasets. This improvement arises because</td>
    </tr>
    <tr>
      <td>loss while maintaining high sample diversity, we proposed</td>
      <td>reconstruction loss provides the generator with additional</td>
    </tr>
    <tr>
      <td>Weighted Learning, a novel method for combining recon-</td>
      <td>direct feedback regarding the disparity between the input</td>
    </tr>
    <tr>
      <td>struction loss and adversarial loss, instead of using a sim-</td>
      <td>training data and the data generated by the model, facilitat-</td>
    </tr>
    <tr>
      <td>ple linear combination. In this section, we investigate the</td>
      <td>ing the rapid generation of data with superior image qual-</td>
    </tr>
  </tbody>
</table>
  <thead>
    <tr>
      <th>have made significant progress in addressing the slow sam-</th>
      <th>Model<br>FID↓Recall↑Time(s)↓</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>pling weakness of diffusion models.Theresultsin Ta-</td>
      <td>5.210.40Ours<br>0.55 (*)</td>
    </tr>
    <tr>
      <td>ble 3 demonstrate that our model further improves upon this</td>
      <td>WDGAN [29]5.940.370.60</td>
    </tr>
    <tr>
      <td>weakness, achieving state-of-the-artrunning speed among</td>
      <td>DDGAN [28]7.640.361.73</td>
    </tr>
    <tr>
      <td>diffusion models while maintainingcompetitivesample</td>
      <td>Score SDE [45]7.23--</td>
    </tr>
    <tr>
      <td>quality. While a few variants of diffusion models, such as</td>
      <td>NVAE [64]29.7--</td>
    </tr>
    <tr>
      <td>Score SDE [44] or DDPM [47], achieve better FID scores</td>
      <td>VAEBM [65]20.4--</td>
    </tr>
    <tr>
      <td>than our model, our model achieves a sampling speed that</td>
      <td>PGGAN [39]8.03--</td>
    </tr>
    <tr>
      <td>is 5000 times faster than Score SDE and 1000 times faster</td>
      <td>VQ-GAN [35]10.2--</td>
    </tr>
  </tbody>
</table>
