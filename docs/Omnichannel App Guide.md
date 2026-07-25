# **The Simple Guide to Omnichannel (App-First Perspective)**

If you are running a business, your customers are everywhere. Some prefer to send an **email**, and others are chatting on your community **Discord**.

Normally, keeping up with this means having different apps open, constantly switching tabs, and inevitably missing messages.

**"Omnichannel" changes this by making the app do all the juggling for you.**

## **1\. What does it look like in the App? (The Simple Explanation)**

To the person using your mobile app, "Omnichannel" feels like magic. It condenses two different communication networks into **one single, beautiful inbox**.

* **The Unified Inbox:** When a customer has a major bug or query, it doesn't matter if they emailed you or posted it in a Discord channel. In your app, it lands as a clean, uniform card on your **Escalation Desk**.  
* **One-Click Replies:** You don't need to open Discord to reply to a Discord user. You simply type your reply inside your app's bottom drawer and hit "Approve & Send."  
* **The Smart Return Trip:** The app is smart enough to know where the message came from. If you reply to an email card, it sends an email. If you reply to a Discord card, your community bot replies directly to that user's message on Discord.

Essentially, **the app hides all the chaotic plumbing** of the internet so you can focus on just talking to your customers in one place.

## **2\. What happens "Under the Hood"? (The Quick Tech Breakdown)**

Behind this smooth mobile interface is a highly synchronized, low-latency automated pipeline. Here is the path a message takes from the customer to your phone:

\[ Customer Message \]   
       │ (Discord or Email)  
       ▼  
 \[ 1\. Channel Listener \] ──(Catches the message immediately)  
       │  
       ▼  
\[ 2\. FastAPI Brain \] ──(Runs AI classification & checks urgency)  
       │  
       ├─► \[ P(C|M) \< 0.8 \] ──► (Drafts and sends a friendly Auto-Reply)  
       │  
       └─► \[ P(C|M) \>= 0.8 \] ──► (Saves to DB as "Critical Escalation")  
                                        │  
                                        ▼  
                               \[ 3\. Expo Mobile Client \]   
                               (Instant live update over SSE)

### **Step 1: The Channel Listeners**

We run lightweight "listeners" for each channel: a **Discord gateway bot** that
hears new messages the moment they're posted, and a **Gmail poller** that checks
the connected mailbox every ~45 seconds. Each one packages a new message into a
neat data bundle (sender name, platform, message text) and forwards it to the
backend. *(An automation tool, n8n, is available as an optional fallback but is
not on the main path.)*

### **Step 2: The Sentiment Brain (FastAPI & LLM)**

The listener sends this data bundle to your **FastAPI backend**, which passes the
message to a local AI Language Model (LLM) to determine if the customer is
frustrated, angry, or has a critical system bug.

Under the hood, we calculate the probability of the message being critical, represented as ![][image1]:

* ![][image2]If the probability is low (![][image3]), the AI drafts a response and handles it automatically.  
* If the probability is high (![][image4]), the backend flags the message as **"Critical"** and writes it into your database.

### **Step 3: The Real-Time Handshake (SSE to Expo)**

To ensure you get the message instantly without draining your phone's battery, we use **Server-Sent Events (SSE)**.

The moment a critical ticket is written to the database, the server pushes a tiny signal down an active pipeline directly to your mobile app. Your phone vibrates with a tactile haptic pulse, your global **Zustand store** updates, and **TanStack Query** instantly renders the card at the top of your screen\!

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHIAAAAaCAYAAABreghKAAAFRklEQVR4Xu1YXYhVVRS+l6Yw+sNsGpqfu8/8wOBYhE0plYGF/ZioZAMq2ks9JD2OlCSFiviURqhPFk0hEoQvEfVQQUMDJihioL0JKjKCg/qiQkVz+z732rlZ7vNz7517HC7ng8U5Z39r/6219tr77FKpQIECLYy+vr6HhoeH79blrYAoiuZQdPlMgXaj/XR57jDGrIDsSXMk+UqlsgAyAsMs9YxT7u7uHsDzLl9/tgDjXUnR5TMFsctnsOEazdUENPAi5CKk6skVyCV5v8aOBgYGHgzUXQj5tb+//1HNObAedPZC/oaMw4E78NwFOQFZgbY/YPu6Xp7gPHp6el7R5UScI4eGhu5BvS8h/4qdqpjbu1rPAcF6L3S+d7qQK2j3LXJdXV3z8P1jb2/vIl2vZqChLyD/oPElqvwpyCUM8qf29vb7XTkHBt3vUL7O1/eBei9BpqiHwXb7nAz+iEyqsWisAxj3YgYR+j7GMeB9i9Yh4hzpgLrzIacgf0G2at4B/a0F/0fIxsK/pm1cMwYHBx9ABxOQM4iKDp9jwygfh0xjAMtcOTvmwLS+A51j7Co8EJd2GcHgL9MYmms2xJEr0ffrkOv1OhIreRXq76ft0ObXmidQHqGNbXRUyMYE90lwR6KEhZEKGlIMehifbT6HAcw1Nmr9SCrjfQxle31dB3ALwE1hUL8lbeRiyAkGkubyAsYw3IgjMcftqP+GscE+HlhRbWwb8jz4syEbOxi75cTyqZCoqkJGNYeyZ41NG0edUzo7Ox/B92kTSIlcfZjct+CmQ7wPcWQwGPJCI46UbHUQ9ujB85AJrDbUXQZ7rOVTbHKbjR3ALYec09tQZtCYJpC7Zbn/ApmCs5925Zw85Dyfvj5hbjn+GPi5mveBCc4JRHCuaMSRKO9D3c85D7HhRZY5nucArlg5T2wJ2diHjOUCbP2M5lLh7YE0PqPqAIX5Hs9JND6mI4QT04P2OA64yolprh5gHOslaDIJ+j0uvzOZIMary5HMZBjfh3xHG6OQG54TyuA2oWyhOPoHE1ixPsA/BjkX118izK398Wd0YqSxm8IBaH2CHbFD6mhOAqAK2aC52YhGHMnVVpEDoNiEp9+busY6cFPJ/id3mZT9kRC70661287bH2OPzhpZHBk3eQcEzZPQ26zL80a9jnT7o8tWXIn4vgEZZSqlk5laydHZJmV/JDxHJuoFYWxun3aRlQVJjjT25JXmyDJ0PoLOy5rQkLT0f5ZIE6auuN+dEOp1ZMXbH71vXqzQnm/79sT3VpOyPxIyh9pTq/f/eJbLX/Nx4IBQZ5KrSnOY2FJjbzv247OseQI6i8HvzmJwpnv0N5JV0PZqzOVh3U4cKnU6UjLZTvfNAML3GWNvrD4uSQqVQEzdH4mKDYZJyHLNJQKDeRyVrrIjF1lZYOy+yoPQbauYzjH2wHQ1wPMA8Cq4Q0n/l3nCOdLEbC0hR8op9Cvj/V55h0ZeDESuXJzDlZq4PxKSnhkM2S5IUOEFY1Nj1RPer76jdUNwg45i7hblXvETY1cmJ/dexV6HcfW/T17XyRuRPVEy+rUNJvy7Y9+RsroOqjq/879adMcgG/mOOT4B7k+ly6vO9a5tDfAbTPhSoXmI7I1GYpRx1fEyGpMbQVpZVMuqny0IrcgmoQ32/IZ21URTwX81dHyS6VlzrYS8HCn2PFrLP/CMAR1vhnxaijnUtAJyciTPDju4/fBdk02HHGz2Qd7UXKsgD0fKmeXwHT0AdnR03IdB7OTpTHOtAMztOYounynIrc+uO+rEAgUKFChQoMXwH4ySzdqCgyojAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADoAAAAZCAYAAABggz2wAAACu0lEQVR4Xu2WzauMURzHZ7qUd4lpuvP2zEyT2Ug0pHQ3JDsvYXFjacHiRhFZWChJ7pWFkBQlIVlYeSnq3rLAvXXtWFi4SvkLlEh8vuac27nH85hn5pmd51vf5jnf8z2/8zvvk8mkSJHiv0WtVmsGQTAKb8D9pVJpoe+JQLZarW6izWV4rVKp7Gi1WvN9U4L4/QMd74XvSHhdLpdbwvdZ+Lxery/3vR6y+E7AqwwkEMEYfOK2TRA/HvL5/OKw2XVRKBTKdPoBHrAaq7KC8hQccb0+yuXyGjyPms3mUqtppTRQBjWscpL4HWG2yUN4r9Fo5Px6F0oAfqXzliNrpe7CCa2Ao8+Btime6WKxuNLVGeRt9GP6ThI/CvasjMMrmknfEIagfbb8RGyyX9Drru6CuiE8P/BOsg1XS+O7iv4Gfb3KSeL7GKDBVvgSjvmz2wmmw6hE/tJd6FgE7cvlF/wOL5k89lhPVJwoPQwDmHdhfg1Ps0WX+YZOMBfDRFiHcRNh5yzC+8AMVnzP0VmrukTxNYuYhjFNYzqqC8f3xIXaEudFWIcdE8nMruhFeAduhm/NYNVuKFF8KrfAGYyH+/EWRXUYpbtQDnjG7YWifNBOof2k3TNTDo0Tpc+Bt6one9m2FsQ4F9ahSeQzZ77k6hZ2tfAd8uvQR+AnONhrfB/2nOpN6voiEngLd5oV2GY1Yi5Aeyzq28jqS/hTds7f7PtoQcyN6K84v6u6iB8L2arztMBB3xAFTQ5tJ+EZq7HlGprtqnn0BcoHg/b5u09xntGOa7DeP5wBBnXexosbv1tkdeMR5Cm8CWu+IQzM+ga8H3UM4D6+p0jigvuvqtL+c/BNHopZaTqDlK+jz/B7xEyGLp9b7iUZJ37P0CDhqGbPrwuDEiOh7SSwO+6fDQv51e5fbZPET5EiRYoUKfqA30s3AGeXBBTtAAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADoAAAAZCAYAAABggz2wAAAC50lEQVR4Xu2WzWsTQRjGE6L4rYjG0HzNJg3mIlKJIpReFPHkF+pB9GYPeigKiuKhiCAiWvUgKuJBEBHxJB4sgkIKHtRWqic9eFCh4F8giCL293ZnynS6m2wSqQf3gYfsPPPOM+/M7LybRCJGjBj/LUqlUlUpdRnegQfz+fwiNyYESc/zNjPmOrxVLBZ31mq1+W5Qy/4EbYGvMT8QZNgO8NsHP+DZk06nl/J8Hj4vl8sr3FgHSeJOwZssRAnBEBy2x7btL7tB4GH4HvZnMpklbkxUZLPZAh6f4CGjcSoraY/BATvWRaFQWEfM42q1usxoOrdhOQhpd+I/DTlRMWTAWzhYqVSWuzHNIAnA70xes2Q5qQdwRE7A0mdAXlNixnO53CpbJ6d76CfkuRP/IKQYtBW+hEPuxI2g/LvlJmKS/YZetnUb9PUR84vYUV7DtaLx7KG/Qd8g7U78G8EUhjq8AbvcABd6wrBEZuk25I1SfnH5A3/Ca8rf7L0mJswnTG8JvMILMDiL0QR3puL2G+jCMBI0YdREuIOLiX2kFyv8SFFaL31/wz8QdpHC4HizIiX9xL4ImjBKIvpEr8D7sBe+04uVcX2d+s+CGMrCGDjutfjZCZswTLdBzFFi6qagyEajnUH7zbhnuh3oE6YHQqoswYPK/67uRkq5Mc3A2AtBE+pEJihseVs3MKdF3BG3D30AfoVd7fpPQRtIsanD3kQbCzTgW7hL+SewzWgksRDtqVCetZzyfEy1rfs3/X00wHMT+ivu7+oW/GeCATvgE33hk25/q5BPEZONwnNGkwImu+3pj76Adr/y799DmvO0dlIW6/zDSZHfReMX1X9OwK5vZOLPJHga7ud5jCQu2Xe96P85+CExCb3Bcgdp30b/wu8xvRlSfO7ahTCK/5xBEiOh7SSwR/62uf2NIPEyrtHYlv1lF3htM8q/pw3Z3d29JtHB/f2nYEd6lP9vJAqvyoJdjxgxYsSIEQGTmYoRx1IR2UgAAAAASUVORK5CYII=>